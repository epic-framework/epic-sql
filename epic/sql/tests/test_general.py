import pandas as pd
import datetime as dt

from epic.sql.general import cnt, gb1ob2d, sql_repr, sql_in, sql_format, sql_if


def test_cnt():
    assert cnt == "COUNT(1) AS cnt"


def test_gb1ob2d():
    assert str(gb1ob2d) == "GROUP BY 1 ORDER BY 2 DESC LIMIT 1000"
    assert str(gb1ob2d(2, 10)) == "GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10"


def test_repr():
    assert sql_repr(None) == "NULL"
    assert sql_repr(pd.NA) == "NULL"
    assert sql_repr(pd.NaT) == "NULL"
    assert sql_repr(float('nan')) == "NULL"
    assert sql_repr(123) == str(123)
    assert sql_repr(123.4) == str(123.4)
    assert sql_repr("hello") == "'hello'"
    assert sql_repr("it's") == '"it\'s"'
    assert sql_repr(b"it's") == 'b"it\'s"'
    assert sql_repr(bytearray(b"it's")) == 'b"it\'s"'
    assert sql_repr(d := dt.date.today()) == f"DATE '{d}'"
    assert sql_repr(t := dt.datetime.now()) == f"DATETIME '{t}'"
    assert sql_repr(t := pd.Timestamp.now('UTC')) == f"TIMESTAMP '{t}'"
    assert sql_repr(range(3)) == "[0, 1, 2]"
    assert sql_repr({'a': 1, 'b': 2}) == "STRUCT(1 AS a, 2 AS b)"
    assert sql_repr(pd.DataFrame([[1, 2], [10, 20]], columns=['A', 'B'])) == \
           'SELECT 1 AS A, 2 AS B UNION ALL SELECT 10, 20'


def test_in():
    assert sql_in(('a', 'b')) == "('a', 'b')"


def test_format():
    assert sql_format('SUM({col}) + {i} AS {col}_value', {'col': ['A', 'B'], 'i': [50, 100]}) == \
           'SUM(A) + 50 AS A_value, SUM(B) + 100 AS B_value'
    assert sql_format('{} = {}', [('a', 'b'), (1, 2)], ' AND ') == 'a = 1 AND b = 2'


def test_if():
    cond = dict(value1="a = 3", value2="a = 4", value3="a IS NULL")
    result = "CASE\nWHEN a = 3 THEN 'value1'\nWHEN a = 4 THEN 'value2'\nWHEN a IS NULL THEN 'value3'\nELSE NULL\nEND"
    assert sql_if(cond) == result
    assert sql_if(cond.items()) == result
    assert sql_if(cond, 'value4') == result.replace("ELSE NULL", "ELSE 'value4'")
    assert sql_if([]) == "NULL"
