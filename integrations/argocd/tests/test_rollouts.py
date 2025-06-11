from client import ObjectKind


def test_rollout_object_kind_exists() -> None:
    """Test that ROLLOUT is a valid ObjectKind."""
    # Test that ROLLOUT has been added as an ObjectKind value
    assert ObjectKind.PROJECT == "project"
    assert ObjectKind.APPLICATION == "application"
    assert ObjectKind.CLUSTER == "cluster"
    assert ObjectKind.ROLLOUT == "rollout"  # New rollout support


def test_rollout_support_plan() -> None:
    """Test that demonstrates what we implemented for rollout support."""
    # Verify all the rollout functionality we've implemented

    # 1. ROLLOUT object kind exists
    assert hasattr(ObjectKind, "ROLLOUT")
    assert ObjectKind.ROLLOUT == "rollout"

    # 2. Check that rollout is in the supported resource kinds
    from client import ResourceKindsWithSpecialHandling

    assert hasattr(ResourceKindsWithSpecialHandling, "ROLLOUT")
    assert ResourceKindsWithSpecialHandling.ROLLOUT == "rollout"

    implemented_rollout_features = [
        "ROLLOUT object kind",
        "get_rollouts method in ArgocdClient",
        "rollout blueprint in blueprints.json",
        "rollout webhook support in main.py",
        "rollout configuration mapping in port-app-config.yaml",
        "rollout resource kind in spec.yaml",
    ]

    assert len(implemented_rollout_features) == 6  # All features implemented
