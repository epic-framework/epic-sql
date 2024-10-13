import pandas as pd
import datetime as dt

from typing import Literal
from google.cloud import bigquery as bq

from ..general import sql_repr


def data_to_temptable(
        data: pd.DataFrame,
        table_name: str,
        expiration: dt.datetime | dt.timedelta | Literal['never'] = dt.timedelta(days=1),
        client: bq.Client | None = None,
) -> None:
    """
    Write a pandas DataFrame to a BigQuery table, and set an expiration timestamp to it.
    If the table already exists, the data must conform with its schema.

    Note: This operation requires `pyarrow` to be installed.

    Parameters
    ----------
    data : DataFrame
        The data to write.

    table_name : str
        The fully qualified name of the table.
        If it does not exist, it will be created.

    expiration : datetime, timedelta or "never", default 1 day.
        When the table is set to expire.
        If a timedelta, it is measured relative to the current time.

    client : bigquery.Client, optional
        The client to use. If not provided, a new client will be created.

    Returns
    -------
    None
    """
    if client is None:
        client = bq.Client()
    client.load_table_from_dataframe(data, table_name).result()
    set_expiration_time(table_name, expiration, client)


def set_expiration_time(
        table_name: str,
        when: dt.datetime | dt.timedelta | Literal['never'],
        client: bq.Client | None = None,
) -> None:
    """
    Set the expiration timestamp for a table.

    Parameters
    ----------
    table_name : str
        The fully qualified name of the table.

    when : datetime, timedelta or "never"
        When the table is set to expire.
        If a timedelta, it is measured relative to the current time.

    client : bigquery.Client, optional
        The client to use. If not provided, a new client will be created.

    Returns
    -------
    None
    """
    if client is None:
        client = bq.Client()
    if when == 'never':
        when = pd.NaT
    elif isinstance(when, dt.timedelta):
        when = pd.Timestamp.now('UTC') + when
    elif not isinstance(when, dt.datetime):
        raise TypeError(f"Unexpected type for `when`: {type(when).__name__}")
    client.query(f"""
        ALTER TABLE `{table_name}`
        SET OPTIONS (
            expiration_timestamp={sql_repr(when)}
        )
    """).result()
