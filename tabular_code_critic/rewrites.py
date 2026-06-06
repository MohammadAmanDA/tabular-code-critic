import ast
from typing import Optional, Tuple


class FilterAggregatePatternFinder(ast.NodeVisitor):
    """
    Finds simple loop-based tabular aggregation patterns and stores suggestions.

    Supported MVP patterns:
    1. filter + sum
    2. filter + mean using list append + sum(list) / len(list)
    """

    def __init__(self):
        self.sum_candidate = None
        self.mean_candidate = None

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self._find_sum_pattern(node)
        self._find_mean_pattern(node)
        self.generic_visit(node)
        return node

    def _find_sum_pattern(self, node: ast.Module) -> None:
        for stmt in node.body:
            if not isinstance(stmt, ast.For):
                continue

            if not (isinstance(stmt.iter, ast.Call) and isinstance(stmt.iter.func, ast.Attribute)):
                continue

            if not (isinstance(stmt.iter.func.value, ast.Name) and stmt.iter.func.value.id == "df"):
                continue

            if stmt.iter.func.attr != "iterrows":
                continue

            if len(stmt.body) != 1 or not isinstance(stmt.body[0], ast.If):
                continue

            if_node = stmt.body[0]

            if len(if_node.body) != 1 or not isinstance(if_node.body[0], ast.AugAssign):
                continue

            aug = if_node.body[0]

            if not isinstance(aug.op, ast.Add):
                continue

            if not isinstance(aug.target, ast.Name):
                continue

            acc_name = aug.target.id

            if not isinstance(aug.value, ast.Subscript):
                continue

            if not (isinstance(aug.value.value, ast.Name) and aug.value.value.id in ("row", "r")):
                continue

            target_col = _extract_str_key(aug.value)
            if target_col is None:
                continue

            cond_expr, cond_col = _extract_simple_condition(if_node.test)
            if cond_expr is None or cond_col is None:
                continue

            self.sum_candidate = {
                "acc_name": acc_name,
                "target_col": target_col,
                "cond_expr": cond_expr,
                "cond_col": cond_col,
            }
            return

    def _find_mean_pattern(self, node: ast.Module) -> None:
        """
        Pattern:
            values = []
            for _, row in df.iterrows():
                if row["age"] > 30:
                    values.append(row["salary"])
            result = sum(values) / len(values)
        """
        body = node.body

        for i in range(len(body) - 2):
            assign_list = body[i]
            for_stmt = body[i + 1]
            assign_mean = body[i + 2]

            # values = []
            if not isinstance(assign_list, ast.Assign):
                continue
            if len(assign_list.targets) != 1 or not isinstance(assign_list.targets[0], ast.Name):
                continue
            list_name = assign_list.targets[0].id

            if not isinstance(assign_list.value, ast.List):
                continue
            if len(assign_list.value.elts) != 0:
                continue

            # for _, row in df.iterrows():
            if not isinstance(for_stmt, ast.For):
                continue
            if not (isinstance(for_stmt.iter, ast.Call) and isinstance(for_stmt.iter.func, ast.Attribute)):
                continue
            if not (isinstance(for_stmt.iter.func.value, ast.Name) and for_stmt.iter.func.value.id == "df"):
                continue
            if for_stmt.iter.func.attr != "iterrows":
                continue

            # body should be: if cond: values.append(row["col"])
            if len(for_stmt.body) != 1 or not isinstance(for_stmt.body[0], ast.If):
                continue
            if_node = for_stmt.body[0]

            if len(if_node.body) != 1 or not isinstance(if_node.body[0], ast.Expr):
                continue

            expr = if_node.body[0].value
            if not (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute)):
                continue

            # values.append(...)
            if not (isinstance(expr.func.value, ast.Name) and expr.func.value.id == list_name):
                continue
            if expr.func.attr != "append":
                continue
            if len(expr.args) != 1:
                continue

            append_arg = expr.args[0]
            if not isinstance(append_arg, ast.Subscript):
                continue
            if not (isinstance(append_arg.value, ast.Name) and append_arg.value.id in ("row", "r")):
                continue

            target_col = _extract_str_key(append_arg)
            if target_col is None:
                continue

            cond_expr, cond_col = _extract_simple_condition(if_node.test)
            if cond_expr is None or cond_col is None:
                continue

            # result = sum(values) / len(values)
            if not isinstance(assign_mean, ast.Assign):
                continue
            if len(assign_mean.targets) != 1 or not isinstance(assign_mean.targets[0], ast.Name):
                continue
            result_name = assign_mean.targets[0].id

            if not isinstance(assign_mean.value, ast.BinOp):
                continue
            if not isinstance(assign_mean.value.op, ast.Div):
                continue

            left = assign_mean.value.left
            right = assign_mean.value.right

            if not (_is_sum_of_name(left, list_name) and _is_len_of_name(right, list_name)):
                continue

            self.mean_candidate = {
                "result_name": result_name,
                "list_name": list_name,
                "target_col": target_col,
                "cond_expr": cond_expr,
                "cond_col": cond_col,
            }
            return


def _extract_str_key(node: ast.Subscript) -> Optional[str]:
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return node.slice.value
    if isinstance(node.slice, ast.Index) and isinstance(node.slice.value, ast.Constant):
        if isinstance(node.slice.value.value, str):
            return node.slice.value.value
    return None


def _extract_simple_condition(node: ast.AST) -> Tuple[Optional[str], Optional[str]]:
    """
    Handle conditions like: row["age"] > 30, row["age"] == 25.
    Return (condition_string, column_name).
    """
    if not isinstance(node, ast.Compare):
        return None, None
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return None, None

    left = node.left
    op = node.ops[0]
    right = node.comparators[0]

    if not isinstance(left, ast.Subscript):
        return None, None
    if not (isinstance(left.value, ast.Name) and left.value.id in ("row", "r")):
        return None, None

    col = _extract_str_key(left)
    if col is None:
        return None, None

    op_map = {
        ast.Gt: ">",
        ast.Lt: "<",
        ast.GtE: ">=",
        ast.LtE: "<=",
        ast.Eq: "==",
        ast.NotEq: "!=",
    }

    op_symbol = None
    for op_type, symbol in op_map.items():
        if isinstance(op, op_type):
            op_symbol = symbol
            break

    if op_symbol is None:
        return None, None

    if not isinstance(right, ast.Constant):
        return None, None

    value_repr = repr(right.value)
    cond_expr = f'df["{col}"] {op_symbol} {value_repr}'
    return cond_expr, col


def _is_sum_of_name(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sum"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == name
    )


def _is_len_of_name(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "len"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == name
    )


def suggest_vectorized_sum(code_str: str) -> Optional[str]:
    tree = ast.parse(code_str)
    finder = FilterAggregatePatternFinder()
    finder.visit(tree)

    c = finder.sum_candidate
    if c is None:
        return None

    return f'{c["acc_name"]} = df.loc[{c["cond_expr"]}, "{c["target_col"]}"].sum()'


def suggest_vectorized_mean(code_str: str) -> Optional[str]:
    tree = ast.parse(code_str)
    finder = FilterAggregatePatternFinder()
    finder.visit(tree)

    c = finder.mean_candidate
    if c is None:
        return None

    return f'{c["result_name"]} = df.loc[{c["cond_expr"]}, "{c["target_col"]}"].mean()'
