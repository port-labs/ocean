from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from actions.prompt_images import (
    MAX_CONCURRENT_FETCHES,
    MAX_IMAGE_BYTES,
    MAX_PROMPT_IMAGES,
    PortImage,
    find_port_images,
    load_prompt_images,
    prompt_without_images,
)
from tests.action_test_helpers import image_block

ASSETS = "https://assets.example.io/organizations/org_1/markdown_image"


def test_finds_the_port_images_of_a_markdown_artifact_with_their_descriptions() -> None:
    prompt = (
        f"### screenshot\n![the  login\npage]({ASSETS}/a.png)\n"
        f"Also {ASSETS}/b.webp, and again ![again]({ASSETS}/a.png)."
    )

    assert find_port_images(prompt) == [
        PortImage(
            f"{ASSETS}/a.png",
            "the login page",
            "organizations/org_1/markdown_image/a.png",
        ),
        PortImage(f"{ASSETS}/b.webp", "", "organizations/org_1/markdown_image/b.webp"),
    ]


def test_ignores_links_that_are_not_port_images() -> None:
    prompt = (
        "![x](https://example.com/cat.png) "
        "https://assets.example.io/organizations/org_1/icon/a.png "
        "https://assets.example.io/markdown_image/a.png"
    )

    assert find_port_images(prompt) == []


def test_ignores_links_with_a_path_before_the_organization() -> None:
    prompt = f"{ASSETS.replace('https://assets.example.io', 'https://assets.example.io/quarantine')}/a.png"

    assert find_port_images(prompt) == []


def test_finding_images_stays_fast_on_hostile_text() -> None:
    for prompt in ("http://" * 200_000, "![" * 200_000, "https://a" + "/b" * 200_000):
        assert find_port_images(prompt) == []


def port_client_answering(*answers: Any) -> MagicMock:
    mock_ocean = MagicMock()
    mock_ocean.port_client.auth.api_url = "https://api.example.io/v1"
    mock_ocean.port_client.auth.headers = AsyncMock(
        return_value={"Authorization": "Bearer t"}
    )
    mock_ocean.port_client.client.get = AsyncMock(side_effect=list(answers))
    return mock_ocean


def response(status: int, body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status,
        json=body,
        request=httpx.Request("GET", "https://api.example.io/v1/asset/content"),
    )


def png(data: str, mime: str = "image/png") -> httpx.Response:
    return response(200, {"ok": True, "data": {"mime": mime, "contentBase64": data}})


@pytest.mark.asyncio
async def test_the_link_becomes_a_label_and_the_image_follows_the_prompt() -> None:
    mock_ocean = port_client_answering(png("AAA"))

    with patch("actions.prompt_images.ocean", mock_ocean):
        loaded = await load_prompt_images(
            f'{{"screenshot": "![the page]({ASSETS}/a.png)"}}'
        )

    assert loaded.prompt == '{"screenshot": "[Image 1: the page]"}'
    assert loaded.blocks == [
        {"type": "text", "text": "Image 1:"},
        image_block("AAA"),
    ]
    assert loaded.failed == []
    call = mock_ocean.port_client.client.get.await_args
    assert call.args == ("https://api.example.io/v1/asset/content",)
    assert call.kwargs["params"] == {
        "fileKey": "organizations/org_1/markdown_image/a.png",
        "maxSizeBytes": MAX_IMAGE_BYTES,
    }
    assert call.kwargs["headers"] == {"Authorization": "Bearer t"}


@pytest.mark.asyncio
async def test_a_link_used_twice_is_one_image_with_one_label() -> None:
    mock_ocean = port_client_answering(png("AAA"))

    with patch("actions.prompt_images.ocean", mock_ocean):
        loaded = await load_prompt_images(f"{ASSETS}/a.png and again {ASSETS}/a.png")

    assert loaded.prompt == "[Image 1] and again [Image 1]"
    assert len(loaded.blocks) == 2
    mock_ocean.port_client.client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_an_image_that_cannot_be_loaded_is_labeled_and_the_others_are_kept() -> (
    None
):
    mock_ocean = port_client_answering(
        response(404, {"ok": False, "error": "asset_not_found"}),
        png("BBB", "image/jpeg"),
        png("CCC", "image/svg+xml"),
    )

    with patch("actions.prompt_images.ocean", mock_ocean):
        loaded = await load_prompt_images(
            f"![gone]({ASSETS}/gone.png) ![b]({ASSETS}/b.jpg) ![c]({ASSETS}/c.svg)"
        )

    assert loaded.prompt == (
        "[Image 1: gone - not attached] [Image 2: b] [Image 3: c - not attached]"
    )
    assert loaded.blocks == [
        {"type": "text", "text": "Image 2:"},
        image_block("BBB", "image/jpeg"),
    ]
    assert loaded.failed == [f"{ASSETS}/gone.png", f"{ASSETS}/c.svg"]


@pytest.mark.asyncio
async def test_a_prompt_without_images_is_left_as_it_is_and_makes_no_request() -> None:
    mock_ocean = port_client_answering()

    with patch("actions.prompt_images.ocean", mock_ocean):
        loaded = await load_prompt_images("fix the bug")

    assert loaded.prompt == "fix the bug"
    assert loaded.blocks == [] and loaded.failed == []
    mock_ocean.port_client.client.get.assert_not_called()


@pytest.mark.asyncio
async def test_images_over_the_limit_are_not_fetched_and_are_labeled() -> None:
    count = MAX_PROMPT_IMAGES + 2
    mock_ocean = port_client_answering(*[png("AAA")] * MAX_PROMPT_IMAGES)
    prompt = " ".join(f"{ASSETS}/{i}.png" for i in range(count))

    with patch("actions.prompt_images.ocean", mock_ocean):
        loaded = await load_prompt_images(prompt)

    assert mock_ocean.port_client.client.get.await_count == MAX_PROMPT_IMAGES
    assert len(loaded.blocks) == 2 * MAX_PROMPT_IMAGES
    assert loaded.failed == [
        f"{ASSETS}/{i}.png" for i in range(MAX_PROMPT_IMAGES, count)
    ]
    assert loaded.prompt.endswith(
        f"[Image {count - 1} - not attached] [Image {count} - not attached]"
    )


@pytest.mark.asyncio
async def test_images_are_fetched_a_few_at_a_time() -> None:
    running = peak = 0

    async def answer(*_: Any, **__: Any) -> httpx.Response:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return png("AAA")

    mock_ocean = port_client_answering()
    mock_ocean.port_client.client.get = AsyncMock(side_effect=answer)
    prompt = " ".join(f"{ASSETS}/{i}.png" for i in range(MAX_PROMPT_IMAGES))

    with patch("actions.prompt_images.ocean", mock_ocean):
        loaded = await load_prompt_images(prompt)

    assert loaded.failed == []
    assert peak == MAX_CONCURRENT_FETCHES


@pytest.mark.asyncio
async def test_images_that_are_not_loaded_in_time_are_not_attached_and_the_rest_are() -> (
    None
):
    async def answer(*_: Any, params: dict[str, Any], **__: Any) -> httpx.Response:
        if params["fileKey"].endswith("slow.png"):
            await asyncio.sleep(10)
        return png("AAA")

    mock_ocean = port_client_answering()
    mock_ocean.port_client.client.get = AsyncMock(side_effect=answer)

    with (
        patch("actions.prompt_images.ocean", mock_ocean),
        patch("actions.prompt_images.LOAD_TIMEOUT_SECONDS", 0.05),
    ):
        loaded = await load_prompt_images(f"{ASSETS}/slow.png {ASSETS}/fast.png")

    assert loaded.prompt == "[Image 1 - not attached] [Image 2]"
    assert loaded.failed == [f"{ASSETS}/slow.png"]
    assert loaded.blocks == [{"type": "text", "text": "Image 2:"}, image_block("AAA")]


def test_a_prompt_without_images_reads_every_link_as_not_attached() -> None:
    prompt = f"see ![the page]({ASSETS}/a.png) and {ASSETS}/b.png and {ASSETS}/a.png"

    assert prompt_without_images(prompt) == (
        "see [Image 1: the page - not attached] and [Image 2 - not attached] "
        "and [Image 1: the page - not attached]"
    )
    assert prompt_without_images("fix the bug") == "fix the bug"


@pytest.mark.asyncio
async def test_each_image_request_has_its_own_timeout() -> None:
    mock_ocean = port_client_answering(png("AAA"))

    with patch("actions.prompt_images.ocean", mock_ocean):
        await load_prompt_images(f"{ASSETS}/a.png")

    assert mock_ocean.port_client.client.get.await_args.kwargs["timeout"] == 10.0


def test_a_description_with_the_brackets_port_escapes_is_one_image() -> None:
    prompt = f"![the \\[beta\\] page]({ASSETS}/a.png)"

    [image] = find_port_images(prompt)

    assert image.alt == "the [beta] page"
    assert prompt_without_images(prompt) == "[Image 1: the [beta] page - not attached]"
