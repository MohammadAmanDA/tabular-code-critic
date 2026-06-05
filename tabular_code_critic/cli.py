import argparse
import pandas as pd
from . import analyze_and_optimize


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and optimize LLM-generated pandas code for a CSV file."
    )
    parser.add_argument("csv_path", help="Path to CSV file")
    parser.add_argument("code_path", help="Path to Python file containing code that uses df")
    args = parser.parse_args()

    df = pd.read_csv(args.csv_path)

    with open(args.code_path, "r", encoding="utf-8") as f:
        code_str = f.read()

    report, suggestions = analyze_and_optimize(df, code_str)

    print("=== Used columns ===")
    for c in report.used_columns:
        print(" ", c)

    print("\n=== Missing columns ===")
    for issue in report.missing_columns:
        print(f"  {issue.column}: {issue.message}")

    print("\n=== Loop issues ===")
    for issue in report.loop_issues:
        print(f"  Line {issue.lineno}: {issue.message}")
        if issue.code_snippet:
            print("    Code:")
            for line in issue.code_snippet.splitlines():
                print("     ", line)

    print("\n=== Suggestions ===")
    for key, suggestion in suggestions.items():
        print(f"  [{key}] {suggestion}")


if __name__ == "__main__":
    main()
