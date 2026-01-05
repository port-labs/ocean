import ast
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class _Violation:
    file: Path
    line: int
    col: int


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _is_payload_organization_subscript(node: ast.AST) -> bool:
    if not isinstance(node, ast.Subscript):
        return False

    if not isinstance(node.value, ast.Name) or node.value.id != "payload":
        return False

    slice_node = node.slice
    if isinstance(slice_node, ast.Constant) and slice_node.value == "organization":
        return True

    return False


def _find_handle_event_violations(file_path: Path) -> list[_Violation]:
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    violations: list[_Violation] = []

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name != "handle_event":
            continue

        for node in ast.walk(fn):
            if _is_payload_organization_subscript(node):
                violations.append(
                    _Violation(
                        file=file_path,
                        line=getattr(node, "lineno", 0),
                        col=getattr(node, "col_offset", 0),
                    )
                )

    return violations


def test_no_handle_event_accesses_payload_organization_directly() -> None:
    """
    Policy test: processors should not assume Organization webhooks.
    Use _GithubAbstractWebhookProcessor.get_webhook_payload_organization(payload) instead.
    """

    integration_dir = (
        Path(__file__).resolve().parents[1]
    )  # .../ocean/integrations/github
    processors_dir = integration_dir / "github" / "webhook" / "webhook_processors"

    violations: list[_Violation] = []
    for file_path in _iter_python_files(processors_dir):
        violations.extend(_find_handle_event_violations(file_path))

    if violations:
        formatted = "\n".join(
            f"- {v.file}:{v.line}:{v.col} uses payload['organization'] inside handle_event()"
            for v in violations
        )
        pytest.fail(
            "Direct access to payload['organization'] inside handle_event() is forbidden.\n"
            "Use get_webhook_payload_organization(payload) instead.\n\n"
            f"{formatted}"
        )
