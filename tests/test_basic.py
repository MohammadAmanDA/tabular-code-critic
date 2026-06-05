import pandas as pd
from tabular_code_critic import analyze_and_optimize


def test_missing_column_detection():
    df = pd.DataFrame({"age": [20, 30], "salary": [1000, 2000]})
    code = """
total = 0
for _, row in df.iterrows():
    if row["age"] > 25:
        total += row["bonus"]
"""
    report, suggestions = analyze_and_optimize(df, code)
    assert "bonus" in report.used_columns
    assert any(issue.column == "bonus" for issue in report.missing_columns)


def test_filter_sum_suggestion():
    df = pd.DataFrame({"age": [20, 35], "salary": [1000, 2000]})
    code = """
total = 0
for _, row in df.iterrows():
    if row["age"] > 30:
        total += row["salary"]
"""
    report, suggestions = analyze_and_optimize(df, code)
    assert "age" in report.used_columns
    assert "salary" in report.used_columns

    # We expect a filter_sum suggestion
    assert "filter_sum" in suggestions
    suggested = suggestions["filter_sum"]
    # Quick smoke check: it should assign to `total` and contain df["age"] > 30
    assert "total =" in suggested
    assert 'df["age"] > 30' in suggested
