from enum import StrEnum


class ObjectKind(StrEnum):
    JOB = "job"
    BUILD = "build"

    @staticmethod
    def get_object_kind_for_event(obj_type: str):
        if obj_type.startswith("item"):
            return ObjectKind.JOB
        elif obj_type.startswith("run"):
            return ObjectKind.BUILD
        else:
            return None
