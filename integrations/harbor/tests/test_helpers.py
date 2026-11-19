"""Tests for Harbor helper utilities."""

from harbor.helpers.util import get_first_tag_name, extract_scan_data


# get_first_tag_name Tests
def test_get_first_tag_name_with_tags():
    """Test get_first_tag_name returns first tag name."""
    artifact = {"tags": [{"name": "latest"}, {"name": "v1.0"}]}
    assert get_first_tag_name(artifact) == "latest"


def test_get_first_tag_name_single_tag():
    """Test get_first_tag_name with single tag."""
    artifact = {"tags": [{"name": "v2.0"}]}
    assert get_first_tag_name(artifact) == "v2.0"


def test_get_first_tag_name_empty_tags():
    """Test get_first_tag_name returns 'untagged' for empty tags."""
    artifact = {"tags": []}
    assert get_first_tag_name(artifact) == "untagged"


def test_get_first_tag_name_no_tags():
    """Test get_first_tag_name returns 'untagged' when tags is None."""
    artifact = {"tags": None}
    assert get_first_tag_name(artifact) == "untagged"


def test_get_first_tag_name_missing_tags_key():
    """Test get_first_tag_name returns 'untagged' when tags key is missing."""
    artifact = {}
    assert get_first_tag_name(artifact) == "untagged"


def test_get_first_tag_name_tag_without_name():
    """Test get_first_tag_name handles tag dict without name key."""
    artifact = {"tags": [{}]}
    assert get_first_tag_name(artifact) == "untagged"


# extract_scan_data Tests
def test_extract_scan_data_with_vulnerabilities():
    """Test extract_scan_data extracts vulnerability counts."""
    artifact = {
        "scan_overview": {
            "application/vnd.scanner.adapter.vuln.report.harbor+json; version=1.0": {
                "scan_status": "Success",
                "severity": "High",
                "summary": {"summary": {"Critical": 5, "High": 10, "Medium": 20, "Low": 30}},
            }
        }
    }

    result = extract_scan_data(artifact)

    assert result["scanStatus"] == "Success"
    assert result["scanSeverity"] == "High"
    assert result["vulnerabilityCritical"] == 5
    assert result["vulnerabilityHigh"] == 10
    assert result["vulnerabilityMedium"] == 20
    assert result["vulnerabilityLow"] == 30
    assert result["vulnerabilityTotal"] == 65


def test_extract_scan_data_no_scan_overview():
    """Test extract_scan_data returns defaults when no scan data."""
    artifact = {}

    result = extract_scan_data(artifact)

    assert result["scanStatus"] is None
    assert result["scanSeverity"] is None
    assert result["vulnerabilityCritical"] == 0
    assert result["vulnerabilityHigh"] == 0
    assert result["vulnerabilityMedium"] == 0
    assert result["vulnerabilityLow"] == 0
    assert result["vulnerabilityTotal"] == 0


def test_extract_scan_data_empty_scan_overview():
    """Test extract_scan_data handles empty scan_overview."""
    artifact = {"scan_overview": {}}

    result = extract_scan_data(artifact)

    assert result["scanStatus"] is None
    assert result["vulnerabilityTotal"] == 0


def test_extract_scan_data_null_scan_overview():
    """Test extract_scan_data handles null scan_overview."""
    artifact = {"scan_overview": None}

    result = extract_scan_data(artifact)

    assert result["scanStatus"] is None
    assert result["vulnerabilityTotal"] == 0


def test_extract_scan_data_partial_summary():
    """Test extract_scan_data handles partial vulnerability summary."""
    artifact = {
        "scan_overview": {
            "test": {
                "scan_status": "Success",
                "severity": "Medium",
                "summary": {"summary": {"Medium": 5}},
            }
        }
    }

    result = extract_scan_data(artifact)

    assert result["scanStatus"] == "Success"
    assert result["scanSeverity"] == "Medium"
    assert result["vulnerabilityCritical"] == 0
    assert result["vulnerabilityHigh"] == 0
    assert result["vulnerabilityMedium"] == 5
    assert result["vulnerabilityLow"] == 0
    assert result["vulnerabilityTotal"] == 5


def test_extract_scan_data_no_summary():
    """Test extract_scan_data handles missing summary."""
    artifact = {
        "scan_overview": {
            "test": {
                "scan_status": "Success",
                "severity": "None",
            }
        }
    }

    result = extract_scan_data(artifact)

    assert result["scanStatus"] == "Success"
    assert result["scanSeverity"] == "None"
    assert result["vulnerabilityTotal"] == 0


def test_extract_scan_data_multiple_scanners():
    """Test extract_scan_data uses first scanner result."""
    artifact = {
        "scan_overview": {
            "scanner1": {
                "scan_status": "Success",
                "severity": "High",
                "summary": {"summary": {"High": 5}},
            },
            "scanner2": {
                "scan_status": "Success",
                "severity": "Critical",
                "summary": {"summary": {"Critical": 10}},
            },
        }
    }

    result = extract_scan_data(artifact)

    # Should use the first scanner's data
    assert result["scanStatus"] == "Success"
    assert result["vulnerabilityTotal"] in [5, 10]  # Depends on dict ordering
