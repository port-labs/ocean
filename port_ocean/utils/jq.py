import re
from typing import Any

import jq  # type: ignore
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.utils.json_compat import (
    JQInputNotJsonSerializableError,
    compile_jq,
    make_json_compatible,
)

_COMPILED_PATTERNS: dict[str, Any] = {}


def _format_filter(pattern: str) -> str:
    """Convert single-quoted string delimiters to double quotes, leaving quotes inside strings untouched."""
    return re.sub(r'(^|\s)\'(?!\s|")|(?<!\s|")\'(\s|$)', r'\1"\2', pattern)


def _compile(pattern: str) -> Any:
    pattern = _format_filter(pattern)
    if not ocean.config.allow_environment_variables_jq_access:
        pattern = "def env: {}; {} as $ENV | " + pattern
    if pattern not in _COMPILED_PATTERNS:
        _COMPILED_PATTERNS[pattern] = jq.compile(pattern)
    return _COMPILED_PATTERNS[pattern]


def evaluate(data: Any, pattern: str) -> Any:
    """Return the first result of a JQ pattern over data, or None (with a warning) when evaluation fails.

    This evaluates integration-side expressions such as request templates and data paths.
    Port entity mapping is done by the data-source-processor, never in Ocean.
    """
    try:
        compiled_pattern = _compile(pattern)
        try:
            results = compile_jq(compiled_pattern, data)
        except JQInputNotJsonSerializableError:
            results = compile_jq(compiled_pattern, make_json_compatible(data))
        return next(iter(results), None)
    except Exception as exc:
        err_msg = str(exc) or repr(exc) or type(exc).__name__
        logger.bind(pattern=pattern, error=err_msg).warning(
            f"JQ evaluation failed - pattern: {pattern}: {err_msg.splitlines()[0]}"
        )
        return None
