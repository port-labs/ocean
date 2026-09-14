import pytest

from port_ocean.tests.smoke.profile_registry import list_profile_names, load_profile


def test_profiles_are_discovered() -> None:
    assert {"once", "polling"}.issubset(set(list_profile_names()))


def test_once_profile_mode() -> None:
    profile = load_profile("once")
    assert profile.mode == "once"
    assert profile.profile_suffix == "once"


def test_polling_profile_mode() -> None:
    profile = load_profile("polling")
    assert profile.mode == "polling"
    assert profile.profile_suffix == "polling"


def test_unknown_profile_raises() -> None:
    with pytest.raises(ValueError, match="Unknown smoke profile"):
        load_profile("does-not-exist")
