"""
Structural guardrails for maixcam/roverMecanum + tools tests.

Run: python tools/check_code_guardrails.py
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
LIB_ROOT = os.path.join(ROOT, "maixcam", "roverMecanum", "lib")
TOOLS_ROOT = os.path.join(ROOT, "tools")


def _py_files(directory: str):
  for dirpath, _dirnames, filenames in os.walk(directory):
    for name in filenames:
      if name.endswith(".py"):
        yield os.path.join(dirpath, name)


def _rel(path: str) -> str:
  return os.path.relpath(path, ROOT).replace("\\", "/")


def check_one_class_per_lib_file() -> list[str]:
  """At most one top-level class per lib module (package __init__ may re-export)."""
  errors = []
  for path in _py_files(LIB_ROOT):
    if os.path.basename(path) == "__init__.py":
      continue
    with open(path, "r", encoding="utf-8") as handle:
      tree = ast.parse(handle.read(), filename=path)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if len(classes) > 1:
      names = ", ".join(node.name for node in classes)
      errors.append(
        f"one-class-per-file: {_rel(path)} has {len(classes)} classes ({names})"
      )
  return errors


def _has_log_call(handler: ast.ExceptHandler) -> bool:
  """Return whether an exception handler records the failure."""
  log_names = {"print", "debug", "info", "warning", "error", "exception", "log"}
  for node in ast.walk(handler):
    if not isinstance(node, ast.Call):
      continue
    function = node.func
    if isinstance(function, ast.Name) and function.id in log_names:
      return True
    if isinstance(function, ast.Attribute):
      if function.attr in log_names or function.attr.startswith(("_log", "_report")):
        return True
  return False


def check_no_silent_except_actions() -> list[str]:
  """Except handlers must log before swallowing with ``pass`` or ``continue``."""
  errors = []
  app_root = os.path.join(ROOT, "maixcam", "roverMecanum")
  for root in (app_root, TOOLS_ROOT):
    for path in _py_files(root):
      with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
      for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
          continue
        swallowed = any(
          isinstance(child, (ast.Pass, ast.Continue))
          for child in ast.walk(node)
        )
        if swallowed and not _has_log_call(node):
          errors.append(
            f"except-silent: {_rel(path)}:{node.lineno} "
            "pass/continue without logging the exception"
          )
  return errors


def check_no_nested_test_classes() -> list[str]:
  """Test modules: no nested ClassDef; prefer one TestCase class per file."""
  errors = []
  for path in _py_files(TOOLS_ROOT):
    name = os.path.basename(path)
    if not name.startswith("test_") or name == "test_rover_menu.py":
      continue
    with open(path, "r", encoding="utf-8") as handle:
      tree = ast.parse(handle.read(), filename=path)
    top_classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if len(top_classes) > 1:
      names = ", ".join(node.name for node in top_classes)
      errors.append(
        f"test-one-class: {_rel(path)} has {len(top_classes)} top-level classes"
        f" ({names}); split the file"
      )
    for cls in top_classes:
      nested = [node for node in cls.body if isinstance(node, ast.ClassDef)]
      if nested:
        nested_names = ", ".join(node.name for node in nested)
        errors.append(
          f"nested-test-class: {_rel(path)}::{cls.name} nests {nested_names}"
        )
  return errors


def main() -> int:
  errors = []
  errors.extend(check_one_class_per_lib_file())
  errors.extend(check_no_silent_except_actions())
  errors.extend(check_no_nested_test_classes())
  if errors:
    print("guardrail FAIL:")
    for line in errors:
      print(f"  - {line}")
    return 1
  print("guardrail OK: one-class-per-file, no except-pass, no nested/multi test classes")
  return 0


if __name__ == "__main__":
  sys.exit(main())
