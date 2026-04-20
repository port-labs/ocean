import pytest
from pydantic import ValidationError

from integration import GithubRepositorySelector


def test_normalized_relations_from_included_relations_alias() -> None:
    selector = GithubRepositorySelector.parse_obj(
        {
            "query": "true",
            "includedRelations": {
                "teams": True,
                "sbom": False,
                "collaborators": {"affiliation": "direct"},
            },
        }
    )

    assert selector.normalized_relations == {
        "teams": {"include": True},
        "collaborators": {"include": True, "affiliation": "direct"},
    }


def test_included_relations_cannot_be_supplied_with_include() -> None:
    with pytest.raises(ValidationError) as exc:
        GithubRepositorySelector.parse_obj(
            {
                "query": "true",
                "include": ["teams"],
                "includedRelations": {"collaborators": {"affiliation": "all"}},
            }
        )

    assert "You cannot supply both 'include' and 'includedRelations'" in str(exc.value)


def test_normalized_relations_falls_back_to_include_list() -> None:
    selector = GithubRepositorySelector.parse_obj(
        {"query": "true", "include": ["teams", "sbom"]}
    )

    assert selector.normalized_relations == {
        "teams": {"include": True},
        "sbom": {"include": True},
    }


def test_included_relations_forbids_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        GithubRepositorySelector.parse_obj(
            {"query": "true", "includedRelations": {"unknown": True}}
        )
