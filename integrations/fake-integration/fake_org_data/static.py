from .types import FakeDepartment


DEPARTMENTS = ["hr", "marketing", "finance", "support", "morpazia"]

FAKE_DEPARTMENTS = [FakeDepartment(id=x, name=x) for x in DEPARTMENTS]
