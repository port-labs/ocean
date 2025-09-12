from datetime import datetime

from aws.core.exporters.organizations.account.models import (
    Account,
    AccountProperties,
    SingleAccountRequest,
    PaginatedAccountRequest,
)


class TestAccountOptions:
    def test_single_account_request_required(self) -> None:
        opts = SingleAccountRequest(region="us-east-1", account_id="111111111111")
        assert opts.region == "us-east-1"
        assert opts.account_id == "111111111111"
        assert opts.include == []

    def test_single_account_request_include(self) -> None:
        opts = SingleAccountRequest(
            region="eu-west-1",
            account_id="111111111111",
            include=["ListParentsAction"],
        )
        assert opts.include == ["ListParentsAction"]

    def test_paginated_account_request_required(self) -> None:
        opts = PaginatedAccountRequest(region="us-west-2", account_id="999999999999")
        assert opts.region == "us-west-2"
        assert opts.account_id == "999999999999"


class TestAccountProperties:
    def test_defaults(self) -> None:
        props = AccountProperties()
        assert props.Name is None
        assert props.Email == ""
        assert props.Tags == []
        assert props.Status == ""
        assert props.Id == ""
        assert props.Arn == ""
        assert props.Parents == []
        assert props.JoinedTimestamp is None

    def test_with_values(self) -> None:
        ts = datetime(2024, 1, 1, 0, 0, 0)
        props = AccountProperties(
            Name="prod",
            Email="a@b.com",
            Parents=[{"Id": "r-root"}],
            Tags=[{"Key": "Env", "Value": "prod"}],
            Status="ACTIVE",
            Id="111111111111",
            Arn="arn:aws:organizations::123456789012:account/o-root/111111111111",
            JoinedTimestamp=ts,
        )

        assert props.Name == "prod"
        assert props.Email == "a@b.com"
        assert props.Parents == [{"Id": "r-root"}]
        assert props.Tags == [{"Key": "Env", "Value": "prod"}]
        assert props.Status == "ACTIVE"
        assert props.Id == "111111111111"
        assert (
            props.Arn
            == "arn:aws:organizations::123456789012:account/o-root/111111111111"
        )
        assert props.JoinedTimestamp == ts


class TestAccountModel:
    def test_type_and_properties(self) -> None:
        acc = Account(Properties=AccountProperties(Name="prod"))
        assert acc.Type == "AWS::Organizations::Account"
        assert acc.Properties.Name == "prod"

    def test_dict_exclude_none(self) -> None:
        props = AccountProperties(Name="prod")
        acc = Account(Properties=props)
        d = acc.dict(exclude_none=True)
        assert d["Type"] == "AWS::Organizations::Account"
        assert d["Properties"]["Name"] == "prod"
