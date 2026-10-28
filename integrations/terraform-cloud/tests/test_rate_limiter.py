import asyncio
import time
from contextlib import suppress

import httpx
import pytest

from rate_limiter import TerraformRateLimiter, budget_key


class TestBudgetKey:
    @pytest.mark.parametrize(
        "path, expected",
        [
            ("/api/v2/workspaces/ws-b6PJa69T989mRSNy/runs", "workspaces/*/runs"),
            ("/api/v2/workspaces/ws-QmFPKBwJErJ3LeQr/runs", "workspaces/*/runs"),
            ("/api/v2/runs/run-CZcmD7eagjhyXavN", "runs/*"),
            (
                "/api/v2/state-versions/sv-g4rqST72reoHjo1P/outputs",
                "state-versions/*/outputs",
            ),
            ("/api/v2/account/details", "account/details"),
            # A resource name that contains a dash is not an id.
            ("/api/v2/state-versions", "state-versions"),
            (
                "/api/v2/organizations/Ocean-Test/workspaces",
                "organizations/Ocean-Test/workspaces",
            ),
            # Only the prefixes HCP Terraform issues collapse, so an organization whose
            # name happens to look like an id keeps its own key.
            (
                "/api/v2/organizations/app-production1/projects",
                "organizations/app-production1/projects",
            ),
        ],
    )
    def test_collapses_only_resource_ids(self, path: str, expected: str) -> None:
        assert budget_key(httpx.URL(f"https://app.terraform.io{path}")) == expected

    def test_every_workspace_shares_one_budget(self) -> None:
        first = budget_key(
            httpx.URL("https://app.terraform.io/api/v2/workspaces/ws-aaaaaaaaaa/runs")
        )
        second = budget_key(
            httpx.URL("https://app.terraform.io/api/v2/workspaces/ws-bbbbbbbbbb/runs")
        )

        assert first == second

    def test_state_file_downloads_share_one_key(self) -> None:
        """Archivist paths are unique per object and must not grow the lock map."""
        first = budget_key(
            httpx.URL("https://archivist.terraform.io/v1/object/dmF1bHQ6djM6YWFh")
        )
        second = budget_key(
            httpx.URL("https://archivist.terraform.io/v1/object/dmF1bHQ6djM6YmJi")
        )

        assert first == second == "non-api"


def headers(limit: str, remaining: str, reset: str) -> httpx.Headers:
    return httpx.Headers(
        {
            "x-ratelimit-limit": limit,
            "x-ratelimit-remaining": remaining,
            "x-ratelimit-reset": reset,
        }
    )


class TestUpdate:
    def test_records_the_reported_budget(self) -> None:
        limiter = TerraformRateLimiter()

        limiter.update(headers("30", "12", "14.4"), "workspaces/*/runs")

        info = limiter._budgets["workspaces/*/runs"]
        assert (info.limit, info.remaining) == (30, 12)
        assert 13.0 < info.seconds_until_reset <= 14.4

    def test_tracks_each_resource_separately(self) -> None:
        limiter = TerraformRateLimiter()

        limiter.update(headers("30", "0", "14"), "workspaces/*/runs")
        limiter.update(headers("30", "29", "1"), "account/details")

        assert limiter._budgets["workspaces/*/runs"].remaining == 0
        assert limiter._budgets["account/details"].remaining == 29

    def test_ignores_responses_without_the_headers(self) -> None:
        limiter = TerraformRateLimiter()

        limiter.update(httpx.Headers({}), "workspaces/*/runs")

        assert limiter._budgets == {}

    def test_ignores_unparsable_headers(self) -> None:
        limiter = TerraformRateLimiter()

        limiter.update(headers("thirty", "12", "14"), "workspaces/*/runs")

        assert limiter._budgets == {}

    def test_does_not_raise_remaining_inside_a_live_window(self) -> None:
        """A response that left the server before the drain must not refill the count."""
        limiter = TerraformRateLimiter()
        limiter.update(headers("30", "1", "14"), "workspaces/*/runs")

        limiter.update(headers("30", "28", "14"), "workspaces/*/runs")

        assert limiter._budgets["workspaces/*/runs"].remaining == 1

    def test_accepts_a_higher_count_once_the_window_has_passed(self) -> None:
        limiter = TerraformRateLimiter()
        limiter.update(headers("30", "1", "0"), "workspaces/*/runs")

        limiter.update(headers("30", "28", "14"), "workspaces/*/runs")

        assert limiter._budgets["workspaces/*/runs"].remaining == 28


class TestBudget:
    @pytest.mark.asyncio
    async def test_does_not_pause_before_anything_is_known(self) -> None:
        limiter = TerraformRateLimiter()

        started = time.monotonic()
        async with limiter.budget("workspaces/*/runs"):
            pass

        assert time.monotonic() - started < 0.1

    @pytest.mark.asyncio
    async def test_pauses_until_the_window_resets_when_spent(self) -> None:
        limiter = TerraformRateLimiter()
        limiter.update(headers("30", "1", "0.2"), "workspaces/*/runs")

        started = time.monotonic()
        async with limiter.budget("workspaces/*/runs"):
            pass

        assert time.monotonic() - started >= 0.2

    @pytest.mark.asyncio
    async def test_does_not_pause_once_the_window_has_passed(self) -> None:
        limiter = TerraformRateLimiter()
        limiter.update(headers("30", "0", "0"), "workspaces/*/runs")

        started = time.monotonic()
        async with limiter.budget("workspaces/*/runs"):
            pass

        assert time.monotonic() - started < 0.1

    @pytest.mark.asyncio
    async def test_a_spent_budget_does_not_apply_to_another_key(self) -> None:
        limiter = TerraformRateLimiter()
        limiter.update(headers("30", "0", "5"), "workspaces/*/runs")

        started = time.monotonic()
        async with limiter.budget("account/details"):
            pass

        assert time.monotonic() - started < 0.1

    @pytest.mark.asyncio
    async def test_a_pausing_resource_does_not_stall_another(self) -> None:
        """One lock per key: a resource mid-pause must not hold up a different one."""
        limiter = TerraformRateLimiter()
        limiter.update(headers("30", "0", "5"), "workspaces/*/runs")

        async def spend_the_paused_resource() -> None:
            async with limiter.budget("workspaces/*/runs"):
                pass

        pausing = asyncio.create_task(spend_the_paused_resource())
        await asyncio.sleep(0.01)

        started = time.monotonic()
        async with limiter.budget("account/details"):
            pass
        elapsed = time.monotonic() - started

        pausing.cancel()
        with suppress(asyncio.CancelledError):
            await pausing

        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_spends_the_budget_before_the_response_corrects_it(self) -> None:
        limiter = TerraformRateLimiter()
        limiter.update(headers("30", "10", "14"), "workspaces/*/runs")

        async with limiter.budget("workspaces/*/runs"):
            pass

        assert limiter._budgets["workspaces/*/runs"].remaining == 9

    @pytest.mark.asyncio
    async def test_spends_the_refreshed_budget_after_a_pause(self) -> None:
        """A response landing during the pause is what the waiter should spend from."""
        limiter = TerraformRateLimiter()
        limiter.update(headers("30", "1", "0.2"), "workspaces/*/runs")

        async def refresh_mid_pause() -> None:
            await asyncio.sleep(0.05)
            limiter._budgets["workspaces/*/runs"].reset_at = time.monotonic()
            limiter.update(headers("30", "30", "14"), "workspaces/*/runs")

        refreshing = asyncio.create_task(refresh_mid_pause())
        async with limiter.budget("workspaces/*/runs"):
            pass
        await refreshing

        assert limiter._budgets["workspaces/*/runs"].remaining == 29
