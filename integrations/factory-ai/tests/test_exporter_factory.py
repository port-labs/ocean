import pytest

from factory_ai.exporter_factory import get_exporter_metadata
from factory_ai.kinds import ObjectKind


def test_get_exporter_metadata_unimplemented_kind() -> None:
    with pytest.raises(NotImplementedError, match="session"):
        get_exporter_metadata(ObjectKind.SESSION)
