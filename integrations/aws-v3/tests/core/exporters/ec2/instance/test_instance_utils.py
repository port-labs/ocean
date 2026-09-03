from aws.core.exporters.ec2.instance.utils import extract_ec2_instances


class TestExtractEc2Instances:
    def test_flattens_reservations(self) -> None:
        response = {
            "Reservations": [
                {"Instances": [{"InstanceId": "i-1"}, {"InstanceId": "i-2"}]},
                {"Instances": [{"InstanceId": "i-3"}]},
            ]
        }

        assert extract_ec2_instances(response) == [
            {"InstanceId": "i-1"},
            {"InstanceId": "i-2"},
            {"InstanceId": "i-3"},
        ]

    def test_returns_empty_list_when_missing(self) -> None:
        assert extract_ec2_instances({}) == []
