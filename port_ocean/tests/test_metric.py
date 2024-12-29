import json
import sys
import pytest


@pytest.mark.metric
def test_metrics() -> None:
    print(sys.argv)
    path = "/tmp/ocean/metric.log"
    dealy = 2
    batch_size = 400
    total_objects = 2000
    with open(path, "r") as file:
        content = file.read()
        magic_string = "integration metrics"
        idx = content.find(magic_string)
        content = content[idx + len(magic_string) :]
        obj = json.loads(content)
        metrics = obj.get("metrics")
        dep = metrics.get("fake-person")
        load = dep.get("load")
        extract = dep.get("extract")
        transform = dep.get("transform")
        assert round(extract.get("duration")) == round(
            ((total_objects / batch_size) * dealy) + 1
        )
        assert extract.get("object_count") == total_objects
        assert load.get("object_count") == total_objects
        assert transform.get("object_count") == total_objects
