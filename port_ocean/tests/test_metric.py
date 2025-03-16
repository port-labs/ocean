import ast
import pytest


@pytest.mark.metric
@pytest.mark.skip(reason="Skipping metric test until we have a way to test the metrics")
def test_metrics() -> None:
    """
    Test that the metrics logged in /tmp/ocean/metric.log match expected values.
    """

    log_path = "/tmp/ocean/metric.log"
    delay = 2
    batch_size = 400
    total_objects = 2000
    magic_string = "prometheus metrics |"

    # Read the file
    with open(log_path, "r") as file:
        content = file.read()

    # Ensure the magic string is present in the content
    assert magic_string in content, f"'{magic_string}' not found in {log_path}"

    # Isolate and parse the JSON object after the magic string
    start_idx = content.rfind(magic_string)
    content_after_magic = content[start_idx + len(magic_string) :]
    obj = ast.literal_eval(content_after_magic)

    # ----------------------------------------------------------------------------
    # 1. Validate Extract Duration (using original delay/batch_size logic)
    # ----------------------------------------------------------------------------
    num_batches = total_objects / batch_size  # e.g., 2000 / 400 = 5
    expected_min_extract_duration = num_batches * delay  # e.g., 5 * 2 = 10

    # Check "fake-person-1" extract duration is > expected_min_extract_duration
    actual_extract_duration = obj.get("duration_seconds__fake-person-1__extract", 0)
    assert round(actual_extract_duration) > round(expected_min_extract_duration), (
        f"Extract duration {actual_extract_duration} not greater than "
        f"{expected_min_extract_duration}"
    )

    # ----------------------------------------------------------------------------
    # 2. Check Durations for Both "fake-person-1" and "fake-department-0"
    # ----------------------------------------------------------------------------
    # -- fake-person-1
    transform_duration_p1 = obj.get("duration_seconds__fake-person-1__transform", 0)
    load_duration_p1 = obj.get("duration_seconds__fake-person-1__load", 0)
    assert (
        transform_duration_p1 > 0
    ), f"Expected transform duration > 0, got {transform_duration_p1}"
    assert load_duration_p1 > 0, f"Expected load duration > 0, got {load_duration_p1}"

    # -- fake-department-0
    extract_duration_dept0 = obj.get("duration_seconds__fake-department-0__extract", 0)
    transform_duration_dept0 = obj.get(
        "duration_seconds__fake-department-0__transform", 0
    )
    load_duration_dept0 = obj.get("duration_seconds__fake-department-0__load", 0)

    assert (
        extract_duration_dept0 > 0
    ), f"Expected department extract duration > 0, got {extract_duration_dept0}"
    assert (
        transform_duration_dept0 > 0
    ), f"Expected department transform duration > 0, got {transform_duration_dept0}"
    assert (
        load_duration_dept0 > 0
    ), f"Expected department load duration > 0, got {load_duration_dept0}"

    # Optionally, check the "init__top_sort" duration too, if it's relevant:
    init_top_sort = obj.get("duration_seconds__init__top_sort", 0)
    assert init_top_sort >= 0, f"Expected init__top_sort >= 0, got {init_top_sort}"

    # ----------------------------------------------------------------------------
    # 3. Check Object Counts
    # ----------------------------------------------------------------------------
    # -- fake-person-1
    person_extract_count = obj.get("object_count__fake-person-1__extract", 0)
    person_load_count = obj.get("object_count__fake-person-1__load", 0)
    assert person_extract_count == 2000.0, (
        f"Expected object_count__fake-person-1__extract=2000.0, "
        f"got {person_extract_count}"
    )
    assert person_load_count == 4000.0, (
        f"Expected object_count__fake-person-1__load=4000.0, "
        f"got {person_load_count}"
    )

    # -- fake-department-0
    dept_extract_count = obj.get("object_count__fake-department-0__extract", 0)
    dept_load_count = obj.get("object_count__fake-department-0__load", 0)
    assert dept_extract_count == 5.0, (
        f"Expected object_count__fake-department-0__extract=5.0, "
        f"got {dept_extract_count}"
    )
    assert dept_load_count == 10.0, (
        f"Expected object_count__fake-department-0__load=10.0, "
        f"got {dept_load_count}"
    )

    # ----------------------------------------------------------------------------
    # 4. Check Input/Upserted Counts
    # ----------------------------------------------------------------------------
    # -- fake-person-1
    input_count_p1 = obj.get("input_count__fake-person-1__load", 0)
    upserted_count_p1 = obj.get("upserted_count__fake-person-1__load", 0)
    assert (
        input_count_p1 == 2000.0
    ), f"Expected input_count__fake-person-1__load=2000.0, got {input_count_p1}"
    assert (
        upserted_count_p1 == 2000.0
    ), f"Expected upserted_count__fake-person-1__load=2000.0, got {upserted_count_p1}"

    # -- fake-department-0
    input_count_dept0 = obj.get("input_count__fake-department-0__load", 0)
    upserted_count_dept0 = obj.get("upserted_count__fake-department-0__load", 0)
    assert (
        input_count_dept0 == 5.0
    ), f"Expected input_count__fake-department-0__load=5.0, got {input_count_dept0}"
    assert (
        upserted_count_dept0 == 5.0
    ), f"Expected upserted_count__fake-department-0__load=5.0, got {upserted_count_dept0}"

    # ----------------------------------------------------------------------------
    # 5. Check Error and Failed Counts
    # ----------------------------------------------------------------------------
    # -- fake-person-1
    error_count_p1 = obj.get("error_count__fake-person-1__load", 0)
    failed_count_p1 = obj.get("failed_count__fake-person-1__load", 0)
    assert (
        error_count_p1 == 0.0
    ), f"Expected error_count__fake-person-1__load=0.0, got {error_count_p1}"
    assert (
        failed_count_p1 == 0.0
    ), f"Expected failed_count__fake-person-1__load=0.0, got {failed_count_p1}"

    # -- fake-department-0
    error_count_dept0 = obj.get("error_count__fake-department-0__load", 0)
    failed_count_dept0 = obj.get("failed_count__fake-department-0__load", 0)
    assert (
        error_count_dept0 == 0.0
    ), f"Expected error_count__fake-department-0__load=0.0, got {error_count_dept0}"
    assert (
        failed_count_dept0 == 0.0
    ), f"Expected failed_count__fake-department-0__load=0.0, got {failed_count_dept0}"

    # ----------------------------------------------------------------------------
    # 6. Check HTTP Request Counts (200s)
    # ----------------------------------------------------------------------------
    # Example: we confirm certain request counters match the sample data provided:
    assert (
        obj.get(
            "http_requests_count__http://host.docker.internal:5555/v1/auth/access_token__init__load__200",
            0,
        )
        == 1.0
    ), "Expected 1.0 for auth access_token 200 requests"
    assert (
        obj.get(
            "http_requests_count__http://host.docker.internal:5555/v1/integration/smoke-test-integration__init__load__200",
            0,
        )
        == 5.0
    ), "Expected 5.0 for integration/smoke-test-integration 200 requests"
    assert (
        obj.get(
            "http_requests_count__http://localhost:8000/integration/department/hr/employees?limit=-1&entity_kb_size=1&latency=2000__fake-person-1__extract__200",
            0,
        )
        == 1.0
    ), "Expected 1.0 for hr/employees?limit=-1 extract 200 requests"
    expected_requests = {
        "http_requests_count__http://localhost:8000/integration/department/marketing/employees?limit=-1&entity_kb_size=1&latency=2000__fake-person-1__extract__200": 1.0,
        "http_requests_count__http://localhost:8000/integration/department/finance/employees?limit=-1&entity_kb_size=1&latency=2000__fake-person-1__extract__200": 1.0,
    }
    for key, expected_val in expected_requests.items():
        assert (
            obj.get(key, 0) == expected_val
        ), f"Expected {expected_val} for '{key}', got {obj.get(key)}"
