from unittest.mock import MagicMock

import pytest

from port_ocean.identity_propagation.oauth_broker import state as state_module
from port_ocean.identity_propagation.oauth_broker.state import InvalidStateError, sign_state, verify_state


@pytest.fixture(autouse=True)
def mock_ocean_config(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_ocean = MagicMock()
    mock_ocean.config.port.client_secret = "test-client-secret"
    mock_ocean.config.identity_propagation.oauth.state_signing_secret = None
    monkeypatch.setattr(state_module, "ocean", mock_ocean)


def test_a_signed_state_round_trips() -> None:
    payload = verify_state(
        sign_state("run_1", "wfnr_1", "jane@acme.com", "org_1")
    )

    assert payload.run_id == "run_1"
    assert payload.node_run_id == "wfnr_1"
    assert payload.actor_id == "jane@acme.com"
    assert payload.org_id == "org_1"


def test_a_tampered_payload_is_rejected() -> None:
    encoded, _, signature = sign_state(
        "run_1", "wfnr_1", "jane@acme.com", "org_1"
    ).partition(".")
    forged = sign_state(
        "run_1", "wfnr_1", "attacker@evil.com", "org_1"
    ).split(".")[0]

    with pytest.raises(InvalidStateError):
        verify_state(f"{forged}.{signature}")

    assert encoded != forged


def test_a_tampered_signature_is_rejected() -> None:
    encoded, _, _ = sign_state(
        "run_1", "wfnr_1", "jane@acme.com", "org_1"
    ).partition(".")

    with pytest.raises(InvalidStateError):
        verify_state(f"{encoded}.bm90LWEtc2lnbmF0dXJl")


def test_a_state_signed_with_another_secret_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = sign_state("run_1", "wfnr_1", "jane@acme.com", "org_1")

    other_ocean = MagicMock()
    other_ocean.config.port.client_secret = "a-different-secret"
    other_ocean.config.identity_propagation.oauth.state_signing_secret = None
    monkeypatch.setattr(state_module, "ocean", other_ocean)

    with pytest.raises(InvalidStateError):
        verify_state(state)


def test_an_expired_state_is_rejected() -> None:
    state = sign_state(
        "run_1", "wfnr_1", "jane@acme.com", "org_1", ttl_seconds=-1
    )

    with pytest.raises(InvalidStateError):
        verify_state(state)


@pytest.mark.parametrize("state", ["", "no-separator", ".", "abc."])
def test_a_malformed_state_is_rejected(state: str) -> None:
    with pytest.raises(InvalidStateError):
        verify_state(state)
