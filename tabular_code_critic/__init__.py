from .analyzer import TabularCodeAnalyzer, AnalysisReport
from .rewrites import suggest_vectorized_sum


def analyze_and_optimize(df, code_str: str):
    """
    High-level API: analyze code, detect issues, and suggest vectorized rewrites.
    Returns (report, suggestions), where suggestions is a dict.
    """
    analyzer = TabularCodeAnalyzer(df)
    report = analyzer.analyze(code_str)

    suggestions = {}
    sum_suggestion = suggest_vectorized_sum(code_str)
    if sum_suggestion is not None:
        suggestions["filter_sum"] = sum_suggestion

    return report, suggestions
