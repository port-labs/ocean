from confluence.helpers.utils import attach_web_url


class TestConfluenceHelpers:
    def test_attach_web_url_uses_webui_path(self) -> None:
        enriched = attach_web_url(
            "https://example.atlassian.net",
            {"id": "1", "_links": {"webui": "/spaces/DOCS"}},
        )
        assert enriched["webUrl"] == "https://example.atlassian.net/wiki/spaces/DOCS"

    def test_attach_web_url_leaves_item_unchanged_without_webui(self) -> None:
        item = {"id": "1", "key": "DOCS"}
        enriched = attach_web_url("https://example.atlassian.net", item)
        assert "webUrl" not in enriched
        assert item == {"id": "1", "key": "DOCS"}
