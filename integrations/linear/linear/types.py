from typing import Annotated

from pydantic import Field

NonEmptyStr = Annotated[str, Field(min_length=1)]
