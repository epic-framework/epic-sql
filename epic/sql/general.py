import pandas as pd

from itertools import chain, repeat
from datetime import date, datetime
from functools import singledispatch
from typing import NewType, Literal, Any
from collections.abc import Iterable, Mapping

from epic.common.general import to_iterable

SQL = NewType('SQL', str)

# Useful shorthand
cnt = SQL("count(1) as cnt")


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
        return SQL(f'group by {gb} order by {self.n + 1} desc limit {self.limit}')


@singledispatch
def sql_repr(obj) -> SQL:
    """
    Represent an object as an SQL expression.
    """
    return SQL(str(obj) if pd.notna(obj) else "NULL")


sql_repr.register(str, lambda s: SQL(f"'{s}'"))
sql_repr.register(date, lambda d: SQL(f"date '{d}'"))
sql_repr.register(datetime, lambda dt: SQL(f"{'datetime' if dt.tzinfo is None else 'timestamp'} '{dt}'"))
sql_repr.register(Iterable, lambda it: SQL(f"[{', '.join(map(sql_repr, it))}]"))
sql_repr.register(Mapping, lambda m: SQL(f"struct({', '.join(f'{sql_repr(v)} as {k}' for k, v in m.items())})"))
sql_repr.register(type(pd.NaT), sql_repr.__wrapped__)  # pd.NaT is an instance of date and datetime, so override


@sql_repr.register
def _(df: pd.DataFrame) -> SQL:
    # Note: The index is not kept
    rows = iter(map(sql_repr, row) for row in df.values)
    rows = chain([(f"{value} as {name}" for name, value in zip(df.columns, next(rows)))], rows)
    return SQL(" union all ".join("select " + ', '.join(row) for row in rows))


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
    >>> sql_format('sum({col}) + {i} as {col}_value', {'col': ['A', 'B'], 'i': [50, 100]})
    'sum(A) + 50 as A_value, sum(B) + 100 as B_value'

    >>> sql_format('{} = {}', [('a', 'b'), (1, 2)], ' and ')
    'a = 1 and b = 2'
    """
    if isinstance(values, Mapping):
        args_iter = repeat(())
        kw_iter = (dict(zip(values.keys(), vals)) for vals in zip(*values.values()))
    else:
        args_iter = zip(*values)
        kw_iter = repeat({})
    return SQL(joiner.join(template.format(*args, **kw) for args, kw in zip(args_iter, kw_iter)))


def sql_if(conditions: Mapping | Iterable[tuple[Any, Any]]) -> SQL:
    """
    Generate an SQL expression which selects the value corresponding to the first matching condition.
    If no condition matches, evaluates to NULL.

    Parameters
    ----------
    conditions : mapping or iterable of pairs
        Successive pairs of values, each with its own condition.
        The conditions are evaluated in order.
        - If a mapping, maps values to conditions.
        - If an iterable, yields pairs of (value, condition). Useful if the values are not hashable.

    Returns
    -------
    string
    """
    if isinstance(conditions, Mapping):
        conditions = conditions.items()
    expression = close_paren = ""
    for value, cond in conditions:
        expression += f"if(({cond}), {sql_repr(value)}, "
        close_paren += ')'
    return SQL(expression + 'NULL' + close_paren)


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
        source_expr = f"select * from {source_expr}"
    if extremum not in ('min', 'max'):
        raise ValueError(f"`extremum` must be one of 'min' or 'max'; got {extremum}")
    order_dir = 'desc' if extremum == 'max' else 'asc'
    return SQL(f"""(
        with ranked as (
            select *, row_number() over(partition by {group_by} order by {value} {order_dir}) as rank_
            from ({source_expr})
        )
        select * from ranked where rank_ = 1
    )""")
