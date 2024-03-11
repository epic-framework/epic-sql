import pandas as pd
import datetime as dt

from epic.sql.general import cnt, gb1ob2d, sql_repr, sql_in, sql_format, sql_if


def test_cnt():
    assert cnt == "count(1) as cnt"


def test_gb1ob2d():
    assert str(gb1ob2d) == "group by 1 order by 2 desc limit 1000"
    assert str(gb1ob2d(2, 10)) == "group by 1, 2 order by 3 desc limit 10"


def test_repr():
    assert sql_repr(None) == "NULL"
    assert sql_repr(pd.NA) == "NULL"
    assert sql_repr(pd.NaT) == "NULL"
    assert sql_repr(float('nan')) == "NULL"
    assert sql_repr(123) == str(123)
    assert sql_repr(123.4) == str(123.4)
    assert sql_repr("hello") == "'hello'"
    assert sql_repr(d := dt.date.today()) == f"date '{d}'"
    assert sql_repr(t := dt.datetime.now()) == f"datetime '{t}'"
    assert sql_repr(t := pd.Timestamp.now('UTC')) == f"timestamp '{t}'"
    assert sql_repr(range(3)) == "[0, 1, 2]"
    assert sql_repr({'a': 1, 'b': 2}) == "struct(1 as a, 2 as b)"
    assert sql_repr(pd.DataFrame([[1, 2], [10, 20]], columns=['A', 'B'])) == \
           'select 1 as A, 2 as B union all select 10, 20'


def test_in():
    assert sql_in(('a', 'b')) == "('a', 'b')"


def test_format():
    assert sql_format('sum({col}) + {i} as {col}_value', {'col': ['A', 'B'], 'i': [50, 100]}) == \
           'sum(A) + 50 as A_value, sum(B) + 100 as B_value'
    assert sql_format('{} = {}', [('a', 'b'), (1, 2)], ' and ') == 'a = 1 and b = 2'


def test_if():
    cond = dict(value1="a = 3", value2="a = 4", value3="a is null")
    result = "if((a = 3), 'value1', if((a = 4), 'value2', if((a is null), 'value3', NULL)))"
    assert sql_if(cond) == result
    assert sql_if(cond.items()) == result


