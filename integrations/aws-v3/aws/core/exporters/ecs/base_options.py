from pydantic import BaseModel, Field
from typing import List


class ExporterOptions(BaseModel):
    region: str = Field(..., description="The AWS region to export resources from")
    include: List[str] = Field(
        default_factory=list,
        description="The resources to include in the export",
    )
