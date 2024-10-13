import pandas as pd

from typing import Any
from collections.abc import Iterable
from google.cloud import bigquery as bq

from epic.jupyter import is_jupyter_notebook
from epic.common.general import coalesce, human_readable


def query_into_df(query: str, client: bq.Client | None = None, verbose: bool = True, **kwargs) -> pd.DataFrame:
    """
    Query BigQuery and return the result as a pandas DataFrame.

    Parameters
    ----------
    query : str
        The query to perform.

    client : bigquery.Client, optional
        The client to use. If not provided, a new client will be created.

    verbose : bool, default True
        Whether to print a description of the performed query.

    **kwargs :
        Sent to query job's `to_dataframe` method.

    Returns
    -------
    DataFrame
    """
    if client is None:
        client = bq.Client()
    job = client.query(query)
    if verbose and 'progress_bar_type' not in kwargs:
        kwargs['progress_bar_type'] = 'tqdm_notebook' if is_jupyter_notebook() else 'tqdm'
    df = job.to_dataframe(**kwargs)
    if verbose:
        print(_describe_query_job(job))
    return df


def query_into_dicts(query: str, client: bq.Client | None = None, verbose: bool = True) -> Iterable[dict[str, Any]]:
    """
    Query BigQuery and yield the resulting rows as dictionaries, mapping column names to values.

    Parameters
    ----------
    query : str
        The query to perform.

    client : bigquery.Client, optional
        The client to use. If not provided, a new client will be created.

    verbose : bool, default True
        Whether to print a description of the performed query.

    Yields
    ------
    dict
    """
    if client is None:
        client = bq.Client()
    job = client.query(query)
    if verbose:
        print(_describe_query_job(job))
    for row in job:
        yield dict(row.items())


def query_into_series_iter(query: str, client: bq.Client | None = None, verbose: bool = True) -> Iterable[pd.Series]:
    """
    Query BigQuery and yield the resulting rows as pandas Series, mapping column names to values.

    Parameters
    ----------
    query : str
        The query to perform.

    client : bigquery.Client, optional
        The client to use. If not provided, a new client will be created.

    verbose : bool, default True
        Whether to print a description of the performed query.

    Yields
    ------
    Series
    """
    yield from map(pd.Series, query_into_dicts(query, client, verbose))


def table_schema(full_table_name: str, client: bq.Client | None = None, **kwargs) -> pd.DataFrame:
    """
    Get the structure of a BigQuery table (column names, data types, etc.), as a pandas DataFrame.

    Parameters
    ----------
    full_table_name : str
        The name of the BigQuery table (containing the project, dataset and table).

    client : bigquery.Client, optional
        The client to use. If not provided, a new client will be created.

    **kwargs :
        Sent to query job's `to_dataframe` method.

    Returns
    -------
    DataFrame
    """
    if full_table_name[0] == full_table_name[-1] == '`':
        full_table_name = full_table_name[1:-1]
    project_dataset, table_name = full_table_name.rsplit('.', 1)
    schema = query_into_df(f"""
        SELECT column_name, data_type, is_nullable = 'YES' is_nullable, 
            is_partitioning_column = 'YES' is_partitioning_column, ordinal_position
        FROM `{project_dataset}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """, client=client, verbose=False, **kwargs).set_index('ordinal_position')
    if schema.index.hasnans:
        schema.index = schema.index.astype(pd.Int32Dtype())
    return schema


# noinspection PyPep8Naming
def _describe_query_job(job: bq.QueryJob, price_per_TiB: float = 6.25) -> str:
    # Updated price per TiB can be found at:
    # https://cloud.google.com/bigquery/pricing#queries
    if not job.done():
        return "Job is still in progress."
    if job.cache_hit:
        return "Query returned results from cache."
    result = job.result()
    billed_factor = 1.01  # We treat billed as "same as processed" bytes if it's up to this multiplier
    billed = f"[billed for {human_readable(job.total_bytes_billed, True, 3)}B] " \
        if job.total_bytes_billed > (job.total_bytes_processed * billed_factor) else ""
    billing_tier = f"[WARNING: billing tier is {job.billing_tier}] " if coalesce(job.billing_tier, 1) == 1 else ""
    usd = job.total_bytes_billed * price_per_TiB / (1 << 40)
    cost = f"${usd:,.2f}" if usd >= 1 else f"{usd * 100:.2f} cents" if usd >= 0.0001 else "free"
    return (
        f"Queried {result.total_rows:,} rows (scanned {human_readable(job.total_bytes_processed, True, 3)}B "
        f"{billed}{billing_tier}for {cost} in {(job.ended - job.started).total_seconds():,.1f} seconds) "
        f"into [dataset:{job.destination.dataset_id}] {job.destination.table_id}"
    )
