from datetime import date, datetime, timezone

from port_ocean.core.utils.json_compat import (
    JQInputNotJsonSerializableError,
    compile_jq,
    make_json_compatible,
)


def test_make_json_compatible_converts_datetime_and_date() -> None:
    dt = datetime(2026, 3, 26, 9, 30, 56, tzinfo=timezone.utc)
    d = date(2026, 3, 26)
    out = make_json_compatible({"dt": dt, "d": d})
    assert out == {"dt": dt.isoformat(), "d": d.isoformat()}


def test_make_json_compatible_recurses_list_and_dict() -> None:
    dt = datetime(2026, 3, 26, 9, 30, 56, tzinfo=timezone.utc)
    out = make_json_compatible({"a": [{"b": dt}]})
    assert out == {"a": [{"b": dt.isoformat()}]}


def test_compile_jq_raises_typed_error_on_not_json_serializable() -> None:
    class DummyCompiled:
        def input_value(self, _data):  # type: ignore[no-untyped-def]
            raise TypeError("Object of type datetime is not JSON serializable")

    try:
        compile_jq(DummyCompiled(), {"x": object()})
        assert False, "Expected JQInputNotJsonSerializableError"
    except JQInputNotJsonSerializableError:
        assert True
