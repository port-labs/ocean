import io
import zipfile

from azure_integration.foundry.core.exporters.skills_exporter import (
    skill_markdown_from_zip,
)


def _zip_with(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def test_skill_markdown_from_zip_prefers_shallow_skill_md() -> None:
    payload = _zip_with(
        {
            "nested/dir/SKILL.md": "# nested",
            "SKILL.md": "# root skill\n\nDo the thing.",
        }
    )
    assert skill_markdown_from_zip(payload) == "# root skill\n\nDo the thing."


def test_skill_markdown_from_zip_empty_or_bad() -> None:
    assert skill_markdown_from_zip(b"") is None
    assert skill_markdown_from_zip(b"not-a-zip") is None
    assert skill_markdown_from_zip(_zip_with({"README.md": "nope"})) is None
