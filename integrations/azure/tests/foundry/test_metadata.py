from azure_integration.foundry.helpers.metadata import merge_metadata, owner_from_metadata


def test_owner_from_metadata_uses_first_matching_key() -> None:
    owner = owner_from_metadata({"team": "ai-coe", "owner": "user@henkel.com"})
    assert owner == "user@henkel.com"


def test_merge_metadata() -> None:
    assert merge_metadata({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
