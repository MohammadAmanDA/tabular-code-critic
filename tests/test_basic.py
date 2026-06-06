import sys
import pandas as pd
from tabular_code_critic import analyze_and_optimize
from tabular_code_critic.cli import main


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
    assert "filter_sum" in suggestions
    suggested = suggestions["filter_sum"]
    assert "total =" in suggested
    assert 'df["age"] > 30' in suggested


def test_cli_outputs_suggestion(tmp_path, capsys):
    csv_path = tmp_path / "sample_data.csv"
    code_path = tmp_path / "sample_code.py"

    csv_path.write_text("age,salary\n20,1000\n35,2000\n40,3000\n", encoding="utf-8")
    code_path.write_text(
        """total = 0
for _, row in df.iterrows():
    if row["age"] > 30:
        total += row["salary"]
""",
        encoding="utf-8",
    )

    old_argv = sys.argv
    try:
        sys.argv = ["prog", str(csv_path), str(code_path)]
        main()
    finally:
        sys.argv = old_argv

    captured = capsys.readouterr()
    out = captured.out

    assert "=== Used columns ===" in out
    assert "age" in out
    assert "salary" in out
    assert "=== Loop issues ===" in out
    assert "df.iterrows()" in out
    assert "=== Suggestions ===" in out
    assert 'total = df.loc[df["age"] > 30, "salary"].sum()' in out


def test_filter_mean_suggestion():
    df = pd.DataFrame({"age": [20, 35, 40], "salary": [1000, 2000, 3000]})
    code = """
values = []
for _, row in df.iterrows():
    if row["age"] > 30:
        values.append(row["salary"])
result = sum(values) / len(values)
"""
    report, suggestions = analyze_and_optimize(df, code)
    assert "filter_mean" in suggestions
    suggested = suggestions["filter_mean"]
    assert 'result = df.loc[df["age"] > 30, "salary"].mean()' == suggested
