from enum import StrEnum

from pydantic import BaseModel

class KomoObjectKind(StrEnum):
    SERVICE = "komodorService"
    HEALTH_MONITOR = "komodorHealthMonitoring"
