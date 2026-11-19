"""Factory Organization users API models.

See https://docs.factory.com/api-reference/organization
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from factory_ai.core.models import FactoryListOptions, FactoryModel, FactoryPagination

# OpenAPI allows 1–100; use the max page size for lean resyncs.
_DEFAULT_LIST_LIMIT = 100


class ListUserOptions(FactoryListOptions):
    """Options for ``GET /api/v0/organization/users``.

    ``cursor`` is owned by the exporter's pagination loop, not OOTB selectors.
    """

    limit: int | None = Field(_DEFAULT_LIST_LIMIT, alias="limit")


class GetUserOptions(BaseModel):
    user_id: str


class User(FactoryModel):
    """Organization member from the Factory Organization Management API.

    List responses document id/email/createdAt/metadata; role and status are
    not on the list contract today (invite uses them) but are retained when
    present via ``extra = allow``.
    """

    id: str
    email: str
    created_at: str = Field(alias="createdAt")
    metadata: dict[str, str]
    first_name: str | None = Field(None, alias="firstName")
    last_name: str | None = Field(None, alias="lastName")
    last_sign_in_at: str | None = Field(None, alias="lastSignInAt")
    role: str | None = None
    status: str | None = None


class ListUsersResponse(FactoryModel):
    users: list[User]
    pagination: FactoryPagination
