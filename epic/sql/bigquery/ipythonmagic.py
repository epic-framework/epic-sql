"""
Import this module to register the %bq magic.
"""
import warnings

from typing import Any
from google.cloud import bigquery as bq
from google.api_core.exceptions import BadRequest

from epic.jupyter.ipython import get_ipython

from .query import query_into_df


class BigQueryMagic:
    """
    IPython magic for querying BigQuery.

    Parameters
    ----------
    client : bigquery.Client, optional
        The client to use. If not provided, a new client will be created.
    """
    def __init__(self, client: bq.Client | None = None):
        self.client = client
        self._name: str | None = None

    def register(self, name: str, ipython=None) -> None:
        """
        Register the magic for use.

        Parameters
        ----------
        name : str
            The name used to activate the magic.

        ipython : InteractiveShell (optional)
            An IPython instance to register with

        Returns
        -------
        None
        """
        if self._name is not None:
            if self._name == name:
                warnings.warn(f"{self} is already registered under name '{name}'; ignoring attempt to re-register")
                return
            else:
                raise Exception(
                    f"{self} is already registered under name '{self._name}'; "
                    f"refusing to register it also under name '{name}'"
                )
        if ipython is None:
            ipython = get_ipython(strict=True)
        ipython.register_magic_function(self.run_magic, 'line_cell', name)
        self._name = name

    @property
    def client(self):
        if self._client is None:
            self._client = bq.Client()
        return self._client

    @client.setter
    def client(self, client: bq.Client | None):
        self._client = client

    def run_magic(self, line: str, cell: str | None = None) -> Any:
        """
        Run the magic using % (one line) or %% (whole cell).

        Parameters
        ----------
        line : str
            Content of the first magic line.

        cell : str, optional
            Content of the rest of the cell.

        Returns
        -------
        Return type depends on the queried content:
        - A DataFrame if a table.
        - A Series if a single column.
        - A single value, if a scalar.
        """
        query = line
        if cell is not None:
            query += "\n" + cell
        query = query.strip()
        if query.startswith("-q"):
            verbose = False
            query = query[2:].strip()
        else:
            verbose = True
        try:
            result = query_into_df(query, self.client, verbose=verbose)
        except BadRequest as exc:
            print(f"BadRequest exception:\n{str(exc)}")
            raise
        if not any(result.shape):
            return
        if result.shape[1] == 1:
            # Convert into a Series
            result = result.iloc[:, 0]
            if result.shape[0] == 1:
                # Convert into a scalar
                result = result.iloc[0]
        return result


def _load_ipython_extension(ipython):
    BigQueryMagic().register("bq", ipython)
