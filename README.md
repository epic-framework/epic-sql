# Epic sql &mdash; Conveniences for working with SQL
[![Epic-sql CI](https://github.com/epic-framework/epic-sql/actions/workflows/ci.yml/badge.svg)](https://github.com/epic-framework/epic-sql/actions/workflows/ci.yml)

## What is it?

The **epic-sql** Python library provides several utilities that make it easier to write SQL code in python.
It can also provide utilities for working with Google BigQuery. 


## Modules

- `general`: Functions for generating SQL expressions in python.
- `bigquery`
  - `query`: Run queries in Google BigQuery; Get information on a BigQuery table.
  - `temptable`: Write data into a BigQuery table; Set expiration time on a table.
  - `ipythonmagic`: Register a convenient IPython magic to query BigQuery and return the results as a pandas DataFrame.
