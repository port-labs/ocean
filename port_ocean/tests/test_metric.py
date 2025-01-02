import json
import pytest


@pytest.mark.metric
def test_metrics() -> None:
    """
    Test that the metrics logged in /tmp/ocean/metric.log match expected values.
    """

    log_path = "/tmp/ocean/metric.log"
    delay = 2
    batch_size = 400
    total_objects = 2000
    magic_string = "integration metrics"

    with open(log_path, "r") as file:
        content = file.read()

    assert magic_string in content, f"'{magic_string}' not found in {log_path}"

    start_idx = content.rfind(magic_string)
    content_after_magic = content[start_idx + len(magic_string) :]

    obj = json.loads(content_after_magic)
    metrics = obj.get("metrics")
    assert metrics, "No 'metrics' key found in the parsed JSON."

    assert "fake-person" in metrics, "'fake-person' key missing in metrics data."
    fake_person = metrics["fake-person"]

    extract = fake_person.get("extract")
    load = fake_person.get("load")
    transform = fake_person.get("transform")

    num_batches = total_objects / batch_size
    expected_min_extract_duration = num_batches * delay
    assert round(extract["duration"]) > round(expected_min_extract_duration), (
        f"Extract duration {extract['duration']} not greater than "
        f"{expected_min_extract_duration}"
    )
    assert extract["object_count"] == total_objects
    assert (
        extract.get("requests", {}).get("200") == num_batches
    ), f"Expected 'requests.200' == {num_batches}, got {extract.get('requests', {}).get('200')}"

    assert load["object_count"] == total_objects
    assert (
        load.get("requests", {}).get("200") == total_objects
    ), f"Expected 'requests.200' == {total_objects}, got {load.get('requests', {}).get('200')}"

    assert transform["object_count"] == total_objects
    assert transform["input_count"] == total_objects
    assert transform["failed_count"] == 0
    assert transform["duration"] > 0

    assert extract["error_count"] == 0
    assert load["error_count"] == 0
    assert transform["error_count"] == 0
