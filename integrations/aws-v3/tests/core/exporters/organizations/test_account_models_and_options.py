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
        assert props.AccountName == ""
        assert props.Email == ""
        assert props.ParentIds == []
        assert props.RoleName is None
        assert props.Tags == []
        assert props.Status == ""
        assert props.Id == ""
        assert props.Arn == ""
        assert props.JoinedTimestamp is None

    def test_with_values(self) -> None:
        ts = datetime(2024, 1, 1, 0, 0, 0)
        props = AccountProperties(
            AccountName="prod",
            Email="a@b.com",
            ParentIds=["r-root"],
            RoleName="OrganizationAccountAccessRole",
            Tags=[{"Key": "Env", "Value": "prod"}],
            Status="ACTIVE",
            Id="111111111111",
            Arn="arn:aws:organizations::123456789012:account/o-root/111111111111",
            JoinedTimestamp=ts,
        )

        assert props.AccountName == "prod"
        assert props.Email == "a@b.com"
        assert props.ParentIds == ["r-root"]
        assert props.RoleName == "OrganizationAccountAccessRole"
        assert props.Tags == [{"Key": "Env", "Value": "prod"}]
        assert props.Status == "ACTIVE"
        assert props.Id == "111111111111"
        assert props.Arn.startswith("arn:aws:organizations::")
        assert props.JoinedTimestamp == ts


class TestAccountModel:
    def test_type_and_properties(self) -> None:
        acc = Account(Properties=AccountProperties(AccountName="prod"))
        assert acc.Type == "AWS::Organizations::Account"
        assert acc.Properties.AccountName == "prod"

    def test_dict_exclude_none(self) -> None:
        props = AccountProperties(AccountName="prod")
        acc = Account(Properties=props)
        d = acc.dict(exclude_none=True)
        assert d["Type"] == "AWS::Organizations::Account"
        assert d["Properties"]["AccountName"] == "prod"
