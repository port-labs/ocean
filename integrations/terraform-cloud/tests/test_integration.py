from integration import OrganizationMembershipSelector, TeamSelector


class TestOrganizationMembershipSelectorToParams:
    def test_no_status_sends_no_params(self) -> None:
        assert OrganizationMembershipSelector(query="true").to_params() == {}

    def test_active_status_maps_to_the_api_filter(self) -> None:
        selector = OrganizationMembershipSelector(query="true", status="active")

        assert selector.to_params() == {"filter[status]": "active"}

    def test_invited_status_maps_to_the_api_filter(self) -> None:
        selector = OrganizationMembershipSelector(query="true", status="invited")

        assert selector.to_params() == {"filter[status]": "invited"}

    def test_search_maps_to_q(self) -> None:
        selector = OrganizationMembershipSelector(query="true", search="jaysins")

        assert selector.to_params() == {"q": "jaysins"}

    def test_emails_are_joined_into_one_filter(self) -> None:
        selector = OrganizationMembershipSelector(
            query="true", emails=["a@example.com", "b@example.com"]
        )

        assert selector.to_params() == {"filter[email]": "a@example.com,b@example.com"}

    def test_every_filter_combines(self) -> None:
        selector = OrganizationMembershipSelector(
            query="true", status="active", search="jaysins", emails=["a@example.com"]
        )

        assert selector.to_params() == {
            "filter[status]": "active",
            "q": "jaysins",
            "filter[email]": "a@example.com",
        }


class TestTeamSelectorToParams:
    def test_no_filters_sends_no_params(self) -> None:
        assert TeamSelector(query="true").to_params() == {}

    def test_search_maps_to_q(self) -> None:
        assert TeamSelector(query="true", search="platform").to_params() == {
            "q": "platform"
        }
