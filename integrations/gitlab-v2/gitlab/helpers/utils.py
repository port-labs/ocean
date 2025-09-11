from enum import StrEnum
from loguru import logger
from typing import Any, Callable, Generator
import json
import yaml
import io
import re
from yaml.events import (
    StreamStartEvent,
    StreamEndEvent,
    DocumentStartEvent,
    DocumentEndEvent,
    SequenceStartEvent,
    SequenceEndEvent,
    MappingStartEvent,
    MappingEndEvent,
    ScalarEvent,
    AliasEvent,
)
import uuid
import os


class ObjectKind(StrEnum):
    PROJECT = "project"
    GROUP = "group"
    ISSUE = "issue"
    MERGE_REQUEST = "merge-request"
    GROUP_WITH_MEMBERS = "group-with-members"
    MEMBER = "member"
    FILE = "file"
    PIPELINE = "pipeline"
    JOB = "job"
    FOLDER = "folder"


def parse_file_content(
    content: str,
    file_path: str,
    context: str,
) -> dict[str, Any]:
    """
    Attempt to parse a string as JSON or YAML. If both parse attempts fail or the content
    is empty, the function returns the original string.

    :param content:    The raw file content to parse.
    :param file_path:  Optional file path for logging purposes (default: 'unknown').
    :param context:    Optional contextual info for logging purposes (default: 'unknown').
    :return:           A dictionary or list (if parsing was successful),
                       or the original string if parsing fails.
    """
    # Quick check for empty or whitespace-only strings
    if not content or content.isspace():
        logger.debug(
            f"File '{file_path}' in '{context}' is empty; returning raw content."
        )
        return {"content": content, "should_resolve_references": False}
    content_path = f"/tmp/ocean/temp_{uuid.uuid4()}.json"
    os.makedirs("/tmp/ocean", exist_ok=True)
    should_resolve_references = False
    # 1) Try JSON
    if file_path.endswith(".json"):
        try:
            json_content = json.loads(content)
            with open(content_path, "w", encoding="utf-8") as f:
                json.dump(json_content, f)
            if "file://" in content:
                should_resolve_references = True
            return (
                {
                    "path": content_path,
                    "should_resolve_references": should_resolve_references,
                }
                if not should_resolve_references
                else {
                    "content": json_content,
                    "should_resolve_references": should_resolve_references,
                }
            )
        except json.JSONDecodeError:
            pass  # Proceed to try YAML

    # 2) Try YAML
    logger.debug(f"Attempting to parse file '{file_path}' in '{context}' as YAML.")
    try:
        with open(content_path, "w", encoding="utf-8") as f:
            yaml_to_json_chunks(content, multiple="array", file_stream=f)
        if "file://" in content:
            should_resolve_references = True
        if not should_resolve_references:
            return {
                "path": content_path,
                "should_resolve_references": should_resolve_references,
            }
        else:
            with open(content_path, "r", encoding="utf-8") as fr:
                json_content = json.load(fr)
                return {
                    "content": (
                        json_content[0] if len(json_content) == 1 else json_content
                    ),
                    "should_resolve_references": should_resolve_references,
                }
    except Exception as e:
        logger.debug(
            f"Failed to parse file '{file_path}' in '{context}' as JSON or YAML: {str(e)}. "
            "Returning raw content."
        )
        return {
            "content": content,
            "should_resolve_references": should_resolve_references,
        }


def enrich_resources_with_project(
    resources: list[dict[str, Any]], project_map: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Enrich resources with their corresponding project data.

    Args:
        resources: List of resources that have a 'project_id' field
        project_map: Dictionary mapping project IDs to project data

    Returns:
        List of resources enriched with '__project' field containing project data.
        Resources without matching projects are included with '__project' set to None.
    """
    enriched_resources = []
    for resource in resources:
        project_id = str(resource["project_id"])
        enriched_resource = {**resource, "__project": project_map.get(project_id)}
        enriched_resources.append(enriched_resource)
    return enriched_resources


# -------- Scalar resolution (lightweight YAML 1.2-ish) --------

_NULLS = {"null", "~", ""}
_TRUE = {"true"}
_FALSE = {"false"}

_int_re = re.compile(
    r"""^[+-]?(
    0
  | [1-9][0-9_]*
)$""",
    re.X,
)

_float_re = re.compile(
    r"""^[+-]?(
    ([0-9][0-9_]*)?\.[0-9_]+([eE][+-]?[0-9_]+)?
  | [0-9][0-9_]*([eE][+-]?[0-9_]+)
)$""",
    re.X,
)


def _clean_underscores(s: str) -> str:
    # YAML allows numeric separators "_"; JSON doesn't.
    return s.replace("_", "")


def scalar_to_json_text(
    val: str | None, tag: str | None, implicit: tuple[bool, bool] | None
) -> str:
    """
    Convert a YAML scalar string to JSON text without building native containers.
    We ignore YAML 1.1 oddities and follow a YAML 1.2-ish core schema.
    """
    if val is None:
        return "null"

    raw = val.strip()

    # If tag explicitly says string, skip heuristics
    if tag and (
        tag.endswith(":str") or tag.endswith(":binary") or tag.endswith(":timestamp")
    ):
        return json.dumps(val)

    # If the value was quoted in the original YAML (implicit[1] is True), treat as literal string
    if implicit is not None and implicit[1]:
        return json.dumps(val)

    # Nulls - only if not quoted (implicit)
    if raw.lower() in _NULLS:
        return "null"

    # Booleans - only if not quoted (implicit)
    low = raw.lower()
    if low in _TRUE:
        return "true"
    if low in _FALSE:
        return "false"

    # Integers
    if _int_re.match(raw):
        try:
            return str(int(_clean_underscores(raw)))
        except ValueError:
            pass  # fall through to string

    # Floats (NaN/Inf represented as strings since JSON lacks them)
    # Only treat as special values if not quoted (implicit)
    if raw.lower() in {"nan", ".nan"}:
        return json.dumps("NaN")
    if raw.lower() in {"inf", "+inf", ".inf", "+.inf"}:
        return json.dumps("Infinity")
    if raw.lower() in {"-inf", "-.inf"}:
        return json.dumps("-Infinity")

    if _float_re.match(raw):
        try:
            # Use repr to avoid locale surprises; still finite numbers only
            float_val = float(_clean_underscores(raw))
            # Check if the float is finite and reasonable (not inf/nan)
            if float_val == float_val and abs(float_val) < 1e308:
                return repr(float_val)
        except ValueError:
            pass

    # Fallback: JSON string
    return json.dumps(val)


# -------- Streaming JSON emitter from YAML events --------


class _Frame:
    __slots__ = ("kind", "index", "expect")  # kind: 'seq'|'map'|'docarray'

    def __init__(self, kind: str, expect: str = "key"):
        self.kind = kind
        self.index = 0
        self.expect = expect  # only for maps: 'key' or 'value'


class YamlToJsonStreamer:
    """
    Stream YAML -> JSON using PyYAML events.
    - No compose/load (no big trees in memory)
    - Emits chunks via a writer callback
    """

    def __init__(self, writer: Callable[[str], None]) -> None:
        self.writer = writer
        self.stack: list[_Frame] = []
        self._doc_count = 0
        self._mode = "single"  # or 'array' or 'newline'

    def set_multiple_mode(self, mode: str) -> None:
        self._mode = mode  # 'array' | 'newline' | 'single'

    # ---- helpers ----
    def _comma_if_needed(self) -> None:
        """Add comma before the next element if we're not at the first element"""
        if not self.stack:
            return
        top = self.stack[-1]
        if top.kind in ("seq", "map", "docarray") and top.index > 0:
            self.writer(",")

    def _open_seq(self) -> None:
        # Only add comma if we're not inside a map expecting a value
        # and we're not at the start of a document in array mode
        if not (
            self.stack
            and self.stack[-1].kind == "map"
            and self.stack[-1].expect == "value"
        ):
            # Don't add comma if we're at the start of a document in array mode
            # (the document start event already handled the comma)
            if not (
                self._mode == "array"
                and self.stack
                and self.stack[-1].kind == "docarray"
                and self._doc_count > 1
            ):
                self._comma_if_needed()
        self.writer("[")
        self.stack.append(_Frame("seq"))

    def _close_seq(self) -> _Frame:
        self.writer("]")
        frame = self.stack.pop()
        if self.stack:
            top = self.stack[-1]
            if top.kind == "map":
                # We just closed a sequence that was the value of a key in a map
                # Set the expectation back to "key" for the next key-value pair
                top.expect = "key"
            top.index += 1
        return frame

    def _open_map(self) -> None:
        # Only add comma if we're not inside a map expecting a value
        # and we're not at the start of a document in array mode
        if not (
            self.stack
            and self.stack[-1].kind == "map"
            and self.stack[-1].expect == "value"
        ):
            # Don't add comma if we're at the start of a document in array mode
            # (the document start event already handled the comma)
            if not (
                self._mode == "array"
                and self.stack
                and self.stack[-1].kind == "docarray"
                and self._doc_count > 1
            ):
                self._comma_if_needed()
        self.writer("{")
        self.stack.append(_Frame("map", expect="key"))

    def _close_map(self) -> _Frame:
        self.writer("}")
        frame = self.stack.pop()
        if self.stack:
            top = self.stack[-1]
            if top.kind == "map":
                # We just closed a map that was the value of a key in another map
                # Set the expectation back to "key" for the next key-value pair
                top.expect = "key"
            top.index += 1
        return frame

    def _emit_scalar(
        self, val: str, tag: str | None, implicit: tuple[bool, bool] | None
    ) -> None:
        # If inside a mapping and expecting a key, we must ensure JSON string key
        if (
            self.stack
            and self.stack[-1].kind == "map"
            and self.stack[-1].expect == "key"
        ):
            self._comma_if_needed()
            # Convert to JSON text; must end up as a *string* key in JSON
            key_json = scalar_to_json_text(val, tag, implicit)
            if not (len(key_json) >= 2 and key_json[0] == '"' and key_json[-1] == '"'):
                # stringify any non-string key json
                key_json = json.dumps(json.loads(key_json))
            self.writer(key_json + ":")
            self.stack[-1].expect = "value"
            # Don't bump index yet; we'll do it after the value is emitted
            return

        # Normal value position - add comma before sequence elements
        if self.stack and self.stack[-1].kind == "seq":
            self._comma_if_needed()
        self.writer(scalar_to_json_text(val, tag, implicit))
        if self.stack:
            top = self.stack[-1]
            if top.kind == "map":
                # just wrote a value
                top.expect = "key"
                top.index += 1
            elif top.kind == "seq":
                top.index += 1

    # ---- main driver ----
    def feed(self, events: list[yaml.events.Event]) -> None:
        # Handle multiple docs wrapper
        docarray_opened = False
        for ev in events:
            if isinstance(ev, DocumentStartEvent):
                if self._mode == "array":
                    if not docarray_opened:
                        self.stack.append(_Frame("docarray"))
                        self.writer("[")
                        docarray_opened = True
                    else:
                        # Only add comma if this is not the first document
                        # and we're not already inside a sequence or mapping
                        if not self.stack or self.stack[-1].kind == "docarray":
                            self._comma_if_needed()
                self._doc_count += 1

            elif isinstance(ev, DocumentEndEvent):
                if self.stack and self.stack[-1].kind == "docarray":
                    self.stack[-1].index += 1

            elif isinstance(ev, SequenceStartEvent):
                self._open_seq()

            elif isinstance(ev, SequenceEndEvent):
                self._close_seq()

            elif isinstance(ev, MappingStartEvent):
                self._open_map()

            elif isinstance(ev, MappingEndEvent):
                self._close_map()

            elif isinstance(ev, ScalarEvent):
                self._emit_scalar(ev.value, ev.tag, ev.implicit)

            elif isinstance(ev, AliasEvent):
                # YAML alias/anchor -> stringify the alias name (low-memory + JSON-safe)
                # Alternative policies are possible (e.g., error out).
                self._emit_scalar(
                    "*" + (ev.anchor or ""), "tag:yaml.org,2002:str", (True, True)
                )

            elif isinstance(ev, StreamStartEvent):
                pass
            elif isinstance(ev, StreamEndEvent):
                pass
            else:
                # Unknown/rare event types -> ignore or raise
                pass

        # Close doc array if used
        if docarray_opened:
            self.writer("]")
            self.stack.pop()  # docarray


def yaml_to_json_chunks(
    yaml_text: str, multiple: str = "array", file_stream: io.TextIOBase | None = None
) -> Generator[str, None, None] | None:
    """
    Convert YAML to JSON and write directly to a file stream if provided,
    otherwise yield JSON text chunks while parsing YAML incrementally.

    Args:
        yaml_text: The YAML text to convert
        multiple: 'array' -> single JSON array of docs
                  'newline' -> one JSON per line
                  'single' -> exactly one doc expected
        file_stream: Optional file-like object to write JSON directly to
    """
    if file_stream is not None:
        # Write directly to file stream - separate function to avoid generator issues
        _yaml_to_json_stream(yaml_text, multiple, file_stream)
        return None
    # Original behavior: yield chunks
    return _yaml_to_json_generator(yaml_text, multiple)


def _yaml_to_json_stream(
    yaml_text: str, multiple: str, file_stream: io.TextIOBase
) -> None:
    """Helper function to write YAML to JSON directly to a file stream."""
    bulk = []

    # Write directly to file stream
    def _write_to_stream(chunk: str) -> None:
        bulk.append(chunk)
        if len(bulk) == 10000:
            file_stream.write("".join(bulk))
            bulk.clear()

    parser = yaml.parse(io.StringIO(yaml_text))
    streamer = YamlToJsonStreamer(_write_to_stream)
    streamer.set_multiple_mode("array" if multiple == "array" else "single")

    streamer.feed(parser)

    # Flush any remaining chunks in the bulk buffer
    if bulk:
        file_stream.write("".join(bulk))
        bulk.clear()

    if multiple == "newline":
        # For newline mode, we need to handle per-document writing
        # Re-parse and write each document separately
        docs = list(iter_yaml_docs_as_single_json(yaml_text))
        for i, jtxt in enumerate(docs):
            if i:
                file_stream.write("\n")
            file_stream.write(jtxt)


def _yaml_to_json_generator(
    yaml_text: str, multiple: str
) -> Generator[str, None, None]:
    """Helper function to generate YAML to JSON chunks."""

    buf: list[str] = []

    def _push(chunk: str) -> None:
        buf.append(chunk)

    parser = yaml.parse(io.StringIO(yaml_text))
    streamer = YamlToJsonStreamer(_push)
    streamer.set_multiple_mode("array" if multiple == "array" else "single")

    streamer.feed(parser)

    if multiple == "newline":
        # Re-parse once but flush per-document; to keep memory tiny, you could
        # instead refactor YamlToJsonStreamer to flush a newline on DocumentEnd.
        # Here we provide a tiny two-pass workaround for simplicity.
        buf.clear()
        # A more memory-tight single-pass variant is included below in the
        # "newline mode" example usage.
        docs = list(iter_yaml_docs_as_single_json(yaml_text))
        for i, jtxt in enumerate(docs):
            if i:
                yield "\n"
            yield jtxt
        return

    # Array/single: yield what we streamed
    out = "".join(buf)
    yield out


# Tiny helper to produce one-JSON-per-doc without storing all docs
def iter_yaml_docs_as_single_json(yaml_text: str) -> Generator[str, None, None]:
    """
    Iterate JSON strings for each YAML document with low memory.
    """
    # We’ll restart a small streamer at each document boundary.
    stream = yaml.parse(io.StringIO(yaml_text))
    buf: list[str] = []

    def flush_doc() -> str | None:
        if buf:
            s = "".join(buf)
            buf.clear()
            return s
        return None

    doc_started = False

    def writer(s: str) -> None:
        buf.append(s)

    local = YamlToJsonStreamer(writer)
    local.set_multiple_mode("single")

    # We proxy events to the local streamer and detect doc boundaries
    from collections import deque

    pending: deque[yaml.events.Event] = deque()

    for ev in stream:
        if isinstance(ev, DocumentStartEvent):
            doc_started = True
            pending.append(ev)
        elif isinstance(ev, DocumentEndEvent):
            pending.append(ev)
            # feed the buffered doc events
            local.feed(list(pending))
            pending.clear()
            s = flush_doc()
            if s is not None:
                yield s
            doc_started = False
        else:
            pending.append(ev)

    # Handle no-document YAML (empty input)
    if not doc_started and not buf and not pending:
        yield "null"
