from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpaceExportOptions:
    """Optional Confluence space filters. Unset values are not sent, so the sync includes every space."""

    space_type: str | None = None
    status: str | None = None
    labels: list[str] | None = None


@dataclass(frozen=True, slots=True)
class PageExportOptions:
    """Controls which pages are fetched.

    ``include_body`` requests each page body as markdown and lowers the page
    size. It is on by default. ``space_ids`` limits the sync to those spaces;
    an empty list means every space.
    """

    include_archived: bool = False
    include_body: bool = True
    space_ids: list[str] | None = None


@dataclass(frozen=True, slots=True)
class UserExportOptions:
    """Which Confluence users to search for.

    ``all`` includes licensed users, external collaborators, and guests.
    """

    site_permission_type: str = "all"
