def load_ipython_extension(ipython):
    """
    Load the %bq magic using BigQueryMagic with default parameters.

    Do not call this function directly.
    Instead, use `%load_ext epic.sql.bigquery` or add it to your IPython configuration.
    """
    from .ipythonmagic import _load_ipython_extension
    _load_ipython_extension(ipython)
