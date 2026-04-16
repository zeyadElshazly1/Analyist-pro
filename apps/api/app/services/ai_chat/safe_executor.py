"""
AST-based safe code executor for LLM-generated pandas queries.

execute_query(df, code) → (result, error_or_None)

Security model: parse the code to an AST, walk every node, and reject anything
not in the explicit whitelist of safe node types.  This is fundamentally more
robust than a regex blacklist because:

  - `import os` is blocked at the AST level (ast.Import not in whitelist)
  - `__import__("os")` is blocked by name (in _BLOCKED_NAMES)
  - `df.__class__` is blocked by the private-attribute rule
  - `with open(...) as f` is blocked (ast.With not in whitelist)
  - `try: exec(...)` is blocked (ast.Try and ast.Name "exec" not in whitelist)
  - Function and class definitions are blocked (ast.FunctionDef, ast.ClassDef)

The namespace exposes only `df`, `pd`, `np`, and safe builtins.
"""
from __future__ import annotations

import ast

import numpy as np
import pandas as pd

_SAFE_BUILTINS: dict = {
    "print": print, "len": len, "range": range, "list": list, "dict": dict,
    "str": str, "int": int, "float": float, "bool": bool, "round": round,
    "abs": abs, "min": min, "max": max, "sum": sum, "sorted": sorted,
    "enumerate": enumerate, "zip": zip, "isinstance": isinstance,
    "type": type, "hasattr": hasattr, "getattr": getattr,
    "set": set, "tuple": tuple, "any": any, "all": all, "map": map,
    "filter": filter, "reversed": reversed,
}

# Only these AST node types are permitted in user code.
_ALLOWED_NODES: frozenset = frozenset({
    # Top-level
    ast.Module, ast.Interactive, ast.Expression,
    # Safe statements
    ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign,
    # Expressions
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call,
    ast.Attribute, ast.Subscript, ast.Slice,
    ast.Name, ast.Constant, ast.NameConstant,  # NameConstant for py<3.8 compat
    ast.List, ast.Tuple, ast.Dict, ast.Set,
    ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
    ast.IfExp, ast.JoinedStr, ast.FormattedValue,
    # Arithmetic operators
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
    ast.Pow, ast.MatMult,
    # Bitwise operators
    ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift,
    # Unary operators
    ast.USub, ast.UAdd, ast.Invert, ast.Not,
    # Boolean operators
    ast.And, ast.Or,
    # Comparison operators
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
    # Context markers
    ast.Load, ast.Store, ast.Del,
    # Limited control flow (no while — prevents infinite loops)
    ast.If, ast.For, ast.comprehension, ast.Starred,
    # Python 3.9+ node wrappers
    ast.Index,  # removed in 3.9 but present in older trees
})

# These names must never appear regardless of node type.
_BLOCKED_NAMES: frozenset[str] = frozenset({
    "__import__", "exec", "eval", "compile", "open", "input",
    "breakpoint", "globals", "locals", "vars", "__builtins__",
    "__spec__", "__loader__", "__build_class__",
    "memoryview", "bytearray",
})


def _audit_ast(tree: ast.AST) -> str | None:
    """
    Walk every node in the AST.
    Return an error string on the first violation found, else None.
    """
    for node in ast.walk(tree):
        node_type = type(node)

        # Reject unlisted node types
        if node_type not in _ALLOWED_NODES:
            return f"Disallowed operation: {node_type.__name__}"

        # Reject blocked names (catches __import__, exec, eval, open, …)
        if isinstance(node, ast.Name) and node.id in _BLOCKED_NAMES:
            return f"Disallowed name: '{node.id}'"

        # Block private-attribute access (df.__class__, pd.__dict__, …)
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return f"Private attribute access not allowed: '.{node.attr}'"

    return None


def execute_query(df: pd.DataFrame, code: str) -> tuple[object, str | None]:
    """
    Safely parse, audit, and execute a snippet of pandas analysis code.

    The code must assign its final answer to a variable named ``result``.
    Returns (result, None) on success, or (None, error_message) on failure.

    The available namespace is: df, pd, np, and a safe builtins subset.
    No imports are allowed — pd and np are pre-injected.
    """
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return None, f"Syntax error: {exc}"

    violation = _audit_ast(tree)
    if violation:
        return None, violation

    namespace: dict = {
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "result": None,
        "__builtins__": _SAFE_BUILTINS,
    }
    try:
        exec(compile(tree, "<query>", "exec"), namespace)  # noqa: S102
        return namespace.get("result"), None
    except Exception as exc:
        return None, str(exc)
