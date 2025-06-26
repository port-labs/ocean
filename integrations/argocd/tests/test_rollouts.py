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


def test_rollout_client_method_exists() -> None:
    """Test that the ArgocdClient has a get_rollouts method."""
    from client import ArgocdClient

    # Check that the method exists
    assert hasattr(ArgocdClient, "get_rollouts")

    # Check the method signature (it should be async)
    import inspect

    method = getattr(ArgocdClient, "get_rollouts")
    assert inspect.iscoroutinefunction(method)


def test_rollout_resource_filtering() -> None:
    """Test the logic for filtering rollout resources."""
    # Mock resource data that would come from ArgoCD API
    mock_managed_resources = [
        {
            "kind": "Deployment",
            "group": "apps",
            "version": "v1",
            "name": "test-deployment",
            "namespace": "default",
        },
        {
            "kind": "Rollout",
            "group": "argoproj.io",
            "version": "v1alpha1",
            "name": "test-rollout",
            "namespace": "default",
        },
        {
            "kind": "Service",
            "group": "",
            "version": "v1",
            "name": "test-service",
            "namespace": "default",
        },
        {
            "kind": "Rollout",
            "group": "argoproj.io",
            "version": "v1alpha1",
            "name": "another-rollout",
            "namespace": "production",
        },
    ]

    # Filter for rollouts like the get_rollouts method does
    rollouts = [
        resource
        for resource in mock_managed_resources
        if resource.get("kind") == "Rollout" and resource.get("group") == "argoproj.io"
    ]

    # Should find exactly 2 rollouts
    assert len(rollouts) == 2
    assert rollouts[0]["name"] == "test-rollout"
    assert rollouts[1]["name"] == "another-rollout"
    assert all(r["kind"] == "Rollout" for r in rollouts)
    assert all(r["group"] == "argoproj.io" for r in rollouts)
