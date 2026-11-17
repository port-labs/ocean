from factory_ai.kinds import ObjectKind


def test_object_kind_values() -> None:
    assert ObjectKind.SESSION.value == "session"
    assert ObjectKind.COMPUTER.value == "computer"
    assert ObjectKind.AUTOMATION.value == "automation"
    assert ObjectKind.SERVICE_ACCOUNT.value == "service-account"
    assert ObjectKind.WIKI.value == "wiki"
