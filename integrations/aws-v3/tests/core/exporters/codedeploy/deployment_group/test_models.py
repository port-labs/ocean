from aws.core.exporters.codedeploy.deployment_group.models import (
    CodeDeployDeploymentGroup,
)


def test_deployment_group_accepts_ec2_and_on_premises_tag_set_objects() -> None:
    """Regression test for PORT-18617.

    AWS's BatchGetDeploymentGroups API returns `ec2TagSet`/`onPremisesTagSet`
    as objects wrapping a `*TagSetList` key (a list of lists of tag filters),
    not as a bare list. Validating a payload shaped like AWS's real response
    previously raised a Pydantic `list_type` error and failed the whole kind.
    """
    deployment_group = CodeDeployDeploymentGroup.model_validate(
        {
            "Type": "AWS::CodeDeploy::DeploymentGroup",
            "Properties": {
                "ApplicationName": "MyApp",
                "DeploymentGroupId": "d87f1777-7de0-47e2-8f89-f193c382ee6d",
                "DeploymentGroupName": "MyGroup",
                "Ec2TagSet": {
                    "ec2TagSetList": [
                        [
                            {
                                "Key": "Environment",
                                "Value": "Production",
                                "Type": "KEY_AND_VALUE",
                            }
                        ]
                    ]
                },
                "OnPremisesTagSet": {"onPremisesTagSetList": []},
            },
        }
    )

    assert deployment_group.Properties.ec2TagSet == {
        "ec2TagSetList": [
            [{"Key": "Environment", "Value": "Production", "Type": "KEY_AND_VALUE"}]
        ]
    }
    assert deployment_group.Properties.onPremisesTagSet == {"onPremisesTagSetList": []}


def test_deployment_group_allows_missing_tag_sets() -> None:
    """ec2TagSet/onPremisesTagSet are optional and should default to None."""
    deployment_group = CodeDeployDeploymentGroup.model_validate(
        {
            "Type": "AWS::CodeDeploy::DeploymentGroup",
            "Properties": {
                "ApplicationName": "MyApp",
                "DeploymentGroupId": "d87f1777-7de0-47e2-8f89-f193c382ee6d",
                "DeploymentGroupName": "MyGroup",
            },
        }
    )

    assert deployment_group.Properties.ec2TagSet is None
    assert deployment_group.Properties.onPremisesTagSet is None
