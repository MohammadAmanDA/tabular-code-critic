import ast
from typing import Optional, Tuple


class FilterSumRewriter(ast.NodeTransformer):
    """
    Look for pattern:
        total = 0
        for ..., row in df.iterrows():
            if <condition using row["col"]>:
                total += row["target_col"]

    and suggest a vectorized alternative.
    """

    def __init__(self):
        super().__init__()
        self.candidate = None  # store info needed for rewrite

    def visit_Module(self, node: ast.Module) -> ast.AST:
        # Walk once to find pattern; for MVP, we don't actually rewrite AST,
        # we just extract a suggested expression as string.
        self.generic_visit(node)
        return node

    def visit_For(self, node: ast.For) -> ast.AST:
        """
        Detect the loop + accumulation pattern.
        Very simplified pattern matcher for MVP.
        """
        # for _, row in df.iterrows():
        if not (isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute)):
            return node

        if not (isinstance(node.iter.func.value, ast.Name) and node.iter.func.value.id == "df"):
            return node

        if node.iter.func.attr != "iterrows":
            return node

        # Expect body: if condition: total += row["target"]
        if len(node.body) != 1 or not isinstance(node.body[0], ast.If):
            return node

        if_node = node.body[0]
        cond = if_node.test
        # expect target assignment inside if: total += row["target"]
        if len(if_node.body) != 1 or not isinstance(if_node.body[0], ast.AugAssign):
            return node

        aug = if_node.body[0]
        if not isinstance(aug.op, ast.Add):
            return node

        # Extract accumulator variable name
        if not isinstance(aug.target, ast.Name):
            return node
        acc_name = aug.target.id

        # Extract row["target_col"]
        if not isinstance(aug.value, ast.Subscript):
            return node
        if not (isinstance(aug.value.value, ast.Name) and aug.value.value.id in ("row", "r")):
            return node

        target_col = _extract_str_key(aug.value)
        if target_col is None:
            return node

        # Condition should be something using row["cond_col"]
        cond_expr, cond_col = _extract_simple_condition(cond)
        if cond_expr is None or cond_col is None:
            return node

        # Store candidate info
        self.candidate = {
            "acc_name": acc_name,
            "target_col": target_col,
            "cond_expr": cond_expr,
            "cond_col": cond_col,
        }

        return node


def _extract_str_key(node: ast.Subscript) -> Optional[str]:
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return node.slice.value
    if isinstance(node.slice, ast.Index) and isinstance(node.slice.value, ast.Constant):
        if isinstance(node.slice.value.value, str):
            return node.slice.value.value
    return None


def _extract_simple_condition(node: ast.AST) -> Tuple[Optional[str], Optional[str]]:
    """
    For MVP, handle conditions like: row["age"] > 30, row["age"] == 25.
    Return (condition_string, column_name).
    """
    if not isinstance(node, ast.Compare):
        return None, None
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return None, None

    left = node.left
    op = node.ops[0]
    right = node.comparators[0]

    # left should be row["col"]
    if not isinstance(left, ast.Subscript):
        return None, None
    if not (isinstance(left.value, ast.Name) and left.value.id in ("row", "r")):
        return None, None

    col = _extract_str_key(left)
    if col is None:
        return None, None

    # reconstruct a simple string representation
    op_str = type(op).__name__  # e.g., Gt, Eq
    # we'll map common ops only
    op_map = {
        "Gt": ">",
        "Lt": "<",
        "GtE": ">=",
        "LtE": "<=",
        "Eq": "==",
        "NotEq": "!=",
    }
    op_symbol = op_map.get(op_str)
    if op_symbol is None:
        return None, None

    # For MVP, require right side to be a Constant
    if not isinstance(right, ast.Constant):
        return None, None

    value_repr = repr(right.value)
    cond_expr = f'df["{col}"] {op_symbol} {value_repr}'
    return cond_expr, col


def suggest_vectorized_sum(code_str: str) -> Optional[str]:
    """
    If a filter+sum candidate is found, return a suggested vectorized expression as string.
    Otherwise return None.
    """
    tree = ast.parse(code_str)
    rewriter = FilterSumRewriter()
    rewriter.visit(tree)
    c = rewriter.candidate
    if c is None:
        return None

    # Accumulator is a scalar; we suggest:
    # acc_name = df.loc[cond_expr, target_col].sum()
    cond_expr = c["cond_expr"]  # already a string like: df["age"] > 30
    target_col = c["target_col"]
    acc_name = c["acc_name"]

    suggestion = f'{acc_name} = df.loc[{cond_expr}, "{target_col}"].sum()'
    return suggestion
