import ast
from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class ColumnIssue:
    column: str
    message: str


@dataclass
class LoopIssue:
    lineno: int
    message: str
    code_snippet: Optional[str] = None


@dataclass
class AnalysisReport:
    used_columns: List[str] = field(default_factory=list)
    missing_columns: List[ColumnIssue] = field(default_factory=list)
    loop_issues: List[LoopIssue] = field(default_factory=list)


class TabularCodeAnalyzer(ast.NodeVisitor):
    def __init__(self, df):
        self.df = df
        self.report = AnalysisReport()

    def analyze(self, code_str: str) -> AnalysisReport:
        tree = ast.parse(code_str)
        self._lines = code_str.splitlines()
        self.visit(tree)
        self._check_missing_columns()
        return self.report

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        """
        Detect usages like df["col"] or row["col"].
        """
        if isinstance(node.value, ast.Name) and node.value.id in ("df", "row", "r"):
            key = None

            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                key = node.slice.value
            elif isinstance(node.slice, ast.Index):
                inner = node.slice.value
                if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                    key = inner.value

            if key is not None and key not in self.report.used_columns:
                self.report.used_columns.append(key)

        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:
        loop_src = self._get_source_snippet(node)
        msg_base = "Loop over DataFrame detected; consider vectorized operations."

        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute):
            if isinstance(node.iter.func.value, ast.Name) and node.iter.func.value.id == "df":
                if node.iter.func.attr in ("iterrows", "itertuples"):
                    self.report.loop_issues.append(
                        LoopIssue(
                            lineno=node.lineno,
                            message=f"{msg_base} Found df.{node.iter.func.attr}().",
                            code_snippet=loop_src,
                        )
                    )

        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
            if (
                len(node.iter.args) == 1
                and isinstance(node.iter.args[0], ast.Call)
                and isinstance(node.iter.args[0].func, ast.Name)
                and node.iter.args[0].func.id == "len"
                and len(node.iter.args[0].args) == 1
                and isinstance(node.iter.args[0].args[0], ast.Name)
                and node.iter.args[0].args[0].id == "df"
            ):
                self.report.loop_issues.append(
                    LoopIssue(
                        lineno=node.lineno,
                        message=f"{msg_base} Found for ... in range(len(df)).",
                        code_snippet=loop_src,
                    )
                )

        self.generic_visit(node)

    def _check_missing_columns(self) -> None:
        df_cols = set(map(str, self.df.columns))
        for col in self.report.used_columns:
            if col not in df_cols:
                self.report.missing_columns.append(
                    ColumnIssue(
                        column=col,
                        message=f"Column '{col}' used in code but not found in df.columns.",
                    )
                )

    def _get_source_snippet(self, node: ast.AST) -> str:
        if not hasattr(self, "_lines"):
            return ""

        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", start)

        if start is None:
            return ""

        start_idx = max(start - 1, 0)
        end_idx = max(end - 1, start_idx)
        return "\n".join(self._lines[start_idx:end_idx + 1])
