import pytest

from azure_integration.helpers.utils import format_query


def test_format_query_strips_quotes_and_whitespace() -> None:
    raw = "\n    '  Resources | where type == \"X\"  '  \n"
    result = format_query(raw)
    assert result == 'Resources | where type == "X"'


def test_format_query_dedents_multiline() -> None:
    raw = """
        Resources
          | where type =~ 'Microsoft.Compute/virtualMachines'
          | project id, name
    """
    result = format_query(raw)
    assert result.startswith("Resources")
    assert "project id, name" in result
    # ensure no leading/trailing whitespace
    assert result == result.strip()
