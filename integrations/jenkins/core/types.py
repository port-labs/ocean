from enum import StrEnum


class ObjectKind(StrEnum):
    BUILD = "build"
    JOB = "job"

    @staticmethod
    def get_object_kind(obj_type: str):
        if obj_type.startswith("item"):
            return ObjectKind.JOB
        elif obj_type.startswith("run"):
            return ObjectKind.BUILD
        else:
            return None
