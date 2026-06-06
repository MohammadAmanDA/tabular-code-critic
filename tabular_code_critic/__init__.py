from .analyzer import TabularCodeAnalyzer, AnalysisReport
from .rewrites import (
    suggest_vectorized_sum,
    suggest_vectorized_mean,
    suggest_vectorized_count,
)


def analyze_and_optimize(df, code_str: str):
    analyzer = TabularCodeAnalyzer(df)
    report = analyzer.analyze(code_str)

    suggestions = {}

    sum_suggestion = suggest_vectorized_sum(code_str)
    if sum_suggestion is not None:
        suggestions["filter_sum"] = sum_suggestion

    mean_suggestion = suggest_vectorized_mean(code_str)
    if mean_suggestion is not None:
        suggestions["filter_mean"] = mean_suggestion

    count_suggestion = suggest_vectorized_count(code_str)
    if count_suggestion is not None:
        suggestions["filter_count"] = count_suggestion

    return report, suggestions
