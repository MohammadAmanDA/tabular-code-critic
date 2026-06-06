\# tabular-code-critic



A small tool that analyzes and optimizes LLM-generated pandas code for tabular data.



\## What it does



Given a CSV file and a Python code snippet that uses a pandas DataFrame named `df`, this tool:



\- detects referenced columns

\- reports missing columns

\- flags slow row-wise loops like `df.iterrows()`

\- suggests simple vectorized pandas rewrites



\## Project status



Current MVP supports:



\- column detection from `df\["col"]` and `row\["col"]`

\- loop detection for:

&#x20; - `df.iterrows()`

&#x20; - `df.itertuples()`

&#x20; - `range(len(df))`

\- rewrite suggestion for a simple filter + sum pattern



\## Setup



Create and activate a virtual environment:

```powershell

python -m venv .venv

.\\.venv\\Scripts\\activate



