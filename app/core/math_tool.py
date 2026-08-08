"""MathCalculator — deterministic, safe arithmetic for grounded answers.

The LLM never computes derived metrics in its head. It writes an expression
and calls ``calculate()``; the result is computed here from the actual query
data. This is the grounding layer that eliminates hallucinated numbers.

Safety: only a whitelisted subset of Python arithmetic is accepted — numbers,
named variables, binary/unary operators, and a small set of pure functions.
No attribute access, subscripts, calls to arbitrary functions, lambdas, or
comprehensions are allowed.
"""

from __future__ import annotations

import ast
import math
import operator
from typing import Any

_BINOPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_FUNCS: dict[str, Any] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "floor": math.floor,
    "ceil": math.ceil,
    "pow": pow,
}


class MathError(ValueError):
    """Raised when an expression cannot be evaluated safely."""


class MathCalculator:
    """Evaluate safe arithmetic expressions with named variables."""

    def calculate(self, expression: str, variables: dict[str, float] | None = None) -> float:
        """Evaluate ``expression`` with ``variables`` bound as names.

        Raises:
            MathError: if the expression uses disallowed syntax or fails to evaluate.
        """
        if not expression or not expression.strip():
            raise MathError("Expression is empty")
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise MathError(f"Invalid expression: {exc}") from exc

        try:
            result = self._eval(tree.body, variables or {})
        except MathError:
            raise
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise MathError(f"Evaluation failed: {exc}") from exc

        if isinstance(result, bool):
            return result
        return float(result)

    def _eval(self, node: ast.AST, variables: dict[str, float]) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise MathError(f"Unsupported constant: {node.value!r}")
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise MathError(f"Unknown variable: {node.id}")
            return variables[node.id]
        if isinstance(node, ast.BinOp):
            op = _BINOPS.get(type(node.op))
            if op is None:
                raise MathError(f"Unsupported operator: {type(node.op).__name__}")
            return op(self._eval(node.left, variables), self._eval(node.right, variables))
        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise MathError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op(self._eval(node.operand, variables))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
                raise MathError("Only whitelisted functions are allowed")
            if node.keywords:
                raise MathError("Keyword arguments are not allowed")
            args = [self._eval(a, variables) for a in node.args]
            return _FUNCS[node.func.id](*args)
        if isinstance(node, ast.Compare):
            # Support chained comparisons like 0 <= x < 1
            left = self._eval(node.left, variables)
            for op_node, comparator in zip(node.ops, node.comparators):
                right = self._eval(comparator, variables)
                op = _COMPARE_OPS.get(type(op_node))
                if op is None:
                    raise MathError(f"Unsupported comparison: {type(op_node).__name__}")
                if not op(left, right):
                    return False
                left = right
            return True
        raise MathError(f"Unsupported syntax: {type(node).__name__}")


_COMPARE_OPS: dict[type[ast.cmpop], Any] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}