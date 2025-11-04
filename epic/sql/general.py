import pandas as pd
import pyarrow as pa

from decimal import Decimal
from itertools import repeat
from datetime import date, datetime
from functools import singledispatch
from typing import NewType, Literal, Any, cast
from collections.abc import Iterable, Mapping

from epic.common.general import to_iterable

SQL = NewType('SQL', str)

# Useful shorthand
cnt = SQL("COUNT(1) AS cnt")


class _StrAsInstance(type):
    def __str__(cls):
        return str(cls())


# noinspection PyPep8Naming
class gb1ob2d(metaclass=_StrAsInstance):
    """
    A useful shorthand for "group by 1 order by 2 desc limit 1000".
    Can also group by more columns, always sorting by the next column after the grouped ones.

    The class itself can also be used as-is, uninstantiated.

    Parameters
    ----------
    n_columns : int, default 1
        The number of columns to group by.

    limit : int, default 1000
        Maximum number of rows to query.

    Returns
    -------
    string
    """
    def __init__(self, n_columns=1, limit=1000):
        self.n = n_columns
        self.limit = limit

    def __str__(self) -> SQL:
        gb = ", ".join(map(str, range(1, self.n + 1)))
        return SQL(f'GROUP BY {gb} ORDER BY {self.n + 1} DESC LIMIT {self.limit}')


def _dtype2sql(dtype: pa.DataType | None) -> str:
    """
    Convert a pyarrow.DataType object to a SQL type string.
    """
    if dtype is None or pa.types.is_null(dtype):
        # Default to STRING as the safest "untyped" type
        # that can be cast from almost anything.
        return "STRING"
    if pa.types.is_string(dtype) or pa.types.is_large_string(dtype):
        return "STRING"
    if pa.types.is_binary(dtype) or pa.types.is_large_binary(dtype):
        return "BYTES"
    if pa.types.is_boolean(dtype):
        return "BOOL"
    if pa.types.is_integer(dtype):
        return "INT64"
    if pa.types.is_floating(dtype):
        return "FLOAT64"
    if pa.types.is_decimal128(dtype):
        return "NUMERIC"
    if pa.types.is_decimal256(dtype):
        return "BIGNUMERIC"
    if pa.types.is_date(dtype):
        return "DATE"
    if pa.types.is_time(dtype):
        return "TIME"
    if pa.types.is_timestamp(dtype):
        return "TIMESTAMP" if cast(pa.TimestampType, dtype).tz else "DATETIME"
    if pa.types.is_dictionary(dtype):
        # A dictionary is an optimization.
        # Its SQL type is just the type of its *values*.
        return _dtype2sql(cast(pa.DictionaryType, dtype).value_type)
    if (
            pa.types.is_list(dtype) or
            pa.types.is_large_list(dtype) or
            pa.types.is_fixed_size_list(dtype) or
            pa.types.is_list_view(dtype) or
            pa.types.is_large_list_view(dtype)
    ):
        return f"ARRAY<{_dtype2sql(cast(pa.ListType, dtype).value_type)}>"
    if pa.types.is_struct(dtype):
        return f"STRUCT<{', '.join(f'`{x.name}` {_dtype2sql(x.type)}' for x in cast(pa.StructType, dtype))}>"
    raise TypeError(f"Unsupported pyarrow type: {dtype}")


@singledispatch
def sql_repr(obj, dtype: pa.DataType | None = None) -> SQL:
    """
    Represent an object as an SQL expression.
    """
    if pd.notna(obj):
        rep = str(obj)
    elif dtype is None:
        rep = "NULL"
    else:
        rep = f"CAST(NULL AS {_dtype2sql(dtype)})"
    return SQL(rep)


sql_repr.register(str, lambda obj, dtype=None: SQL(repr(obj)))
sql_repr.register(bytes, lambda obj, dtype=None: SQL(str(obj)))
sql_repr.register(bytearray, lambda obj, dtype=None: sql_repr(bytes(obj), dtype))


@sql_repr.register(date)
@sql_repr.register(datetime)
@sql_repr.register(Decimal)
def _sql_typed_scalar_repr(obj, dtype: pa.DataType | None = None) -> SQL:
    if obj is pd.NaT:
        return sql_repr(None, dtype=dtype or pa.timestamp('ns'))
    return SQL(f"{_dtype2sql(dtype or pa.scalar(obj).type)} '{obj}'")


@sql_repr.register
def _sql_iterable_repr(obj: Iterable, dtype: pa.DataType | None = None) -> SQL:
    items = list(obj)
    sql_type = _dtype2sql(dtype)
    is_array = sql_type.startswith("ARRAY")
    if not items and is_array:
        return SQL(f"{sql_type}[]")
    val_type = cast(pa.ListType, dtype).value_type if is_array else pa.infer_type(items)
    return SQL(f"[{', '.join(sql_repr(x, dtype=val_type) for x in items)}]")


@sql_repr.register
def _sql_mapping_repr(obj: Mapping, dtype: pa.DataType | None = None) -> SQL:
    sql_type = _dtype2sql(dtype)
    is_struct = sql_type.startswith("STRUCT")
    if not obj and is_struct:
        return SQL(f"CAST(NULL AS {sql_type})")
    expressions = []
    if is_struct:
        for field in cast(pa.StructType, dtype):
            value = obj.get(field.name, None)
            expressions.append(f"{sql_repr(value, dtype=field.type)} AS `{field.name}`")
    else:
        for key, value in obj.items():
            expressions.append(f"{sql_repr(value)} AS `{key}`")
    return SQL(f"STRUCT({', '.join(expressions)})")


@sql_repr.register
def _sql_dataframe_repr(obj: pd.DataFrame, dtype: pa.DataType | None = None) -> SQL:
    if obj.empty:
        raise ValueError("Cannot represent an empty DataFrame as a SQL table expression")
    try:
        schema = pa.Table.from_pandas(obj, preserve_index=False).schema
    except Exception as e:
        raise TypeError(f"Pyarrow failed to infer DataFrame schema: {e}") from e
    rows = []
    for i, row in enumerate(obj.to_numpy(dtype=object)):
        values = []
        for name, value in zip(obj.columns, row):
            sql_val = sql_repr(value, dtype=schema.field(name).type)
            values.append(f"{sql_val} AS `{name}`" if i == 0 else sql_val)
        rows.append(f"SELECT {', '.join(values)}")
    return SQL("\nUNION ALL\n".join(rows))


def sql_in(values, sort: bool = True) -> SQL:
    """
    Convert an iterable of items (or a single item) to an SQL expression suitable
    for use after the "IN" operator.

    Parameters
    ----------
    values : iterable or a single item
        Items to convert to SQL.

    sort : bool, default True
        Whether to sort the items.

    Returns
    -------
    string
    """
    items = map(sql_repr, to_iterable(values))
    if sort:
        items = sorted(items)
    return SQL(f"({', '.join(items)})")


def sql_format(template: str, values: Mapping[str, Iterable] | Iterable[Iterable], joiner: str = ', ') -> SQL:
    """
    Generate an SQL expression based on a template applied repetitively.

    Parameters
    ----------
    template : str
        The template to format.
        Should be compatible with the `str.format` function, i.e. contain `{key}` expressions
        if `values` is a mapping or `{}` (or `{0}`, `{1}`, ...) expressions if `values` is
        an iterable.

    values : mapping of str to iterable or iterable of iterables
        The values to apply to the template.

    joiner: str, default ", "
        The expression joining the repeating applications of the template over the values.

    Returns
    -------
    string

    Examples
    --------
    >>> sql_format('SUM({col}) + {i} AS {col}_value', {'col': ['A', 'B'], 'i': [50, 100]})
    'SUM(A) + 50 AS A_value, SUM(B) + 100 AS B_value'

    >>> sql_format('{} = {}', [('a', 'b'), (1, 2)], ' AND ')
    'a = 1 AND b = 2'
    """
    if isinstance(values, Mapping):
        args_iter = repeat(())
        kw_iter = (dict(zip(values.keys(), vals)) for vals in zip(*values.values()))
    else:
        args_iter = zip(*values)
        kw_iter = repeat({})
    return SQL(joiner.join(template.format(*args, **kw) for args, kw in zip(args_iter, kw_iter)))


def sql_if(conditions: Mapping | Iterable[tuple[Any, Any]], else_=None) -> SQL:
    """
    Generate an SQL expression which selects the value corresponding to the first matching condition.

    Parameters
    ----------
    conditions : mapping or iterable of pairs
        Successive pairs of values, each with its own condition.
        The conditions are evaluated in order.
        - If a mapping, maps values to conditions.
        - If an iterable, yields pairs of (value, condition). Useful if the values are not hashable.

    else_ : optional, default None
        The value if no condition matches.

    Returns
    -------
    string
    """
    if isinstance(conditions, Mapping):
        conditions = conditions.items()
    cases = [f"WHEN {cond} THEN {sql_repr(value)}" for value, cond in conditions]
    else_ = sql_repr(else_)
    return SQL("\n".join(["CASE", *cases, f"ELSE {else_}", "END"]) if cases else else_)


def select_by_extremum(source_expr: str, group_by: str, value: str, extremum: Literal['min', 'max'] = 'max') -> SQL:
    """
    Generate an SQL expression for selecting table rows for which a value is minimal or maximal,
    after grouping by some expression.

    Parameters
    ----------
    source_expr : str
        The source of the query.
        Can be a table name or a query expression.

    group_by : str
        The expression or column name to group by.

    value : str
        The expression or column name which should be extremal for each group.

    extremum : {'min', 'max'}, default 'max'
        Whether `value` should be minimal or maximal for each group.

    Returns
    -------
    string
    """
    if " " not in source_expr:
        source_expr = f"SELECT * FROM {source_expr}"
    if extremum not in ('min', 'max'):
        raise ValueError(f"`extremum` must be one of 'min' or 'max'; got {extremum!r}")
    order_dir = 'DESC' if extremum == 'max' else 'ASC'
    return SQL(f"""(
        SELECT *
        FROM ({source_expr})
        QUALIFY ROW_NUMBER() OVER(PARTITION BY {group_by} ORDER BY {value} {order_dir}) = 1
    )""")
