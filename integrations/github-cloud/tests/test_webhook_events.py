import pytest
import dataclasses
from github_cloud.webhook.events import RepositoryEvents, OrganizationEvents

def test_repository_events_default_values():
    events = RepositoryEvents()
    assert events.push is True
    assert events.pull_request is True
    assert events.issues is True
    assert events.release is True
    assert events.member is True

def test_repository_events_custom_values():
    events = RepositoryEvents(
        push=False,
        pull_request=False,
        issues=False,
        release=False,
        member=False
    )
    assert events.push is False
    assert events.pull_request is False
    assert events.issues is False
    assert events.release is False
    assert events.member is False

def test_repository_events_to_dict():
    events = RepositoryEvents()
    event_dict = events.to_dict()
    assert event_dict == {
        "push": True,
        "pull_request": True,
        "issues": True,
        "release": True,
        "workflow": True,
        "member": True
    }

def test_organization_events_default_values():
    events = OrganizationEvents()
    assert events.member is True
    assert events.membership is True
    assert events.organization is True
    assert events.team is True
    assert events.team_add is True
    assert events.repository is True

def test_organization_events_custom_values():
    events = OrganizationEvents(
        member=False,
        membership=False,
        organization=False,
        team=False,
        team_add=False,
        repository=False
    )
    assert events.member is False
    assert events.membership is False
    assert events.organization is False
    assert events.team is False
    assert events.team_add is False
    assert events.repository is False

def test_organization_events_to_dict():
    events = OrganizationEvents()
    event_dict = events.to_dict()
    assert event_dict == {
        "member": True,
        "membership": True,
        "organization": True,
        "team": True,
        "team_add": True,
        "repository": True
    }

def test_repository_events_immutable():
    events = RepositoryEvents()
    with pytest.raises(dataclasses.FrozenInstanceError):
        events.push = False

def test_organization_events_immutable():
    events = OrganizationEvents()
    with pytest.raises(dataclasses.FrozenInstanceError):
        events.member = False
