from enum import StrEnum


class CloudControlResourceScope(StrEnum):
    AUTO = "auto"
    REGIONAL = "regional"
    GLOBAL = "global"
