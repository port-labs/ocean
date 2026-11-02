import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse

import httpx
from anthropic.types.beta.sessions.beta_managed_agents_base64_image_source_param import (
    BetaManagedAgentsBase64ImageSourceParam,
)
from anthropic.types.beta.sessions.beta_managed_agents_image_block_param import (
    BetaManagedAgentsImageBlockParam,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block_param import (
    BetaManagedAgentsTextBlockParam,
)
from loguru import logger
from port_ocean.context.ocean import ocean

# The images uploaded to Port that a prompt links to, for example in a markdown artifact:
# https://<asset-domain>/organizations/<orgId>/markdown_image/<file>
# The host has no path, so the file key is always `organizations/<orgId>/markdown_image/<file>`, and the pattern stays linear.
_URL = r"https?://[^/\s)\]\"'<>]+/organizations/[^/\s)\]\"'<>]+/markdown_image/[\w%-]+(?:\.[\w%-]+)*"
# Port escapes `[` and `]` in the description of an image it creates.
_ESCAPE = re.compile(r"\\(.)")
# A markdown image, or a bare link.
_IMAGE_LINK = re.compile(
    rf"!\[(?P<alt>(?:[^\]\\]|\\.){{0,500}})\]\((?P<md>{_URL})\)|(?P<bare>{_URL})"
)

MAX_PROMPT_IMAGES = 10
# Few at a time: each image is a few MB of base64 in memory. All of them within the timeout: the run waits for them.
MAX_CONCURRENT_FETCHES = 4
# One image can't use up the time of the others: the whole load has a larger budget than one request.
REQUEST_TIMEOUT_SECONDS = 10.0
LOAD_TIMEOUT_SECONDS = 20.0
# Anthropic takes images of up to 5 MB, as base64: 3.75 MB of image.
MAX_IMAGE_BYTES = 5 * 1024 * 1024 * 3 // 4
SUPPORTED_MEDIA_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)

ImageContent = BetaManagedAgentsTextBlockParam | BetaManagedAgentsImageBlockParam


@dataclass(frozen=True)
class PortImage:
    url: str
    alt: str
    file_key: str


@dataclass(frozen=True)
class PromptImages:
    """A prompt whose Port image links read as labels, and the images those labels name.

    `blocks` follow the prompt in the message: a text block "Image N:" and the image, for each image that was loaded.
    `failed` are the links of the images that are not attached: not loaded in time, not supported, or over the limit.
    """

    prompt: str
    blocks: list[ImageContent] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def _file_key(url: str) -> str:
    return unquote(urlparse(url).path).lstrip("/")


def find_port_images(prompt: str) -> list[PortImage]:
    """The distinct Port images the prompt links to, in order of appearance."""
    images: dict[str, PortImage] = {}
    for match in _IMAGE_LINK.finditer(prompt):
        url = match.group("md") or match.group("bare")
        alt = " ".join(_ESCAPE.sub(r"\1", match.group("alt") or "").split())
        if url not in images:
            images[url] = PortImage(url, alt, _file_key(url))
    return list(images.values())


def _relabel(prompt: str, found: list[PortImage], attached: set[str]) -> str:
    labels = {}
    for number, image in enumerate(found, start=1):
        text = f"Image {number}: {image.alt}" if image.alt else f"Image {number}"
        labels[image.url] = (
            f"[{text}]" if image.url in attached else f"[{text} - not attached]"
        )

    def relabel(match: re.Match[str]) -> str:
        return labels.get(match.group("md") or match.group("bare"), match.group(0))

    return _IMAGE_LINK.sub(relabel, prompt)


def prompt_without_images(prompt: str) -> str:
    """The prompt for a message that carries no images: every link reads as an image that is not attached."""
    return _relabel(prompt, find_port_images(prompt), attached=set())


async def _fetch_image(file_key: str) -> BetaManagedAgentsImageBlockParam:
    """The image as a base64 content block. Port reads the organization from the token, so only its images come back."""
    port_client = ocean.port_client
    response = await port_client.client.get(
        f"{port_client.auth.api_url}/asset/content",
        params={"fileKey": file_key, "maxSizeBytes": MAX_IMAGE_BYTES},
        headers=await port_client.auth.headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json().get("data") or {}
    media_type = data.get("mime")
    content = data.get("contentBase64")
    if media_type not in SUPPORTED_MEDIA_TYPES or not content:
        raise ValueError(f"unsupported image type {media_type!r}")
    return BetaManagedAgentsImageBlockParam(
        type="image",
        source=BetaManagedAgentsBase64ImageSourceParam(
            type="base64", media_type=media_type, data=content
        ),
    )


async def _fetch_images(
    file_keys: list[str],
) -> list[BetaManagedAgentsImageBlockParam | BaseException]:
    """The images in order, or why one is missing. Fetched a few at a time, and all within the timeout."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def fetch(file_key: str) -> BetaManagedAgentsImageBlockParam:
        async with semaphore:
            return await _fetch_image(file_key)

    tasks = [asyncio.create_task(fetch(file_key)) for file_key in file_keys]
    _, pending = await asyncio.wait(tasks, timeout=LOAD_TIMEOUT_SECONDS)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    return [
        (
            asyncio.TimeoutError(f"not loaded within {LOAD_TIMEOUT_SECONDS:g}s")
            if task in pending
            else (task.exception() or task.result())
        )
        for task in tasks
    ]


async def load_prompt_images(prompt: str) -> PromptImages:
    """Loads the Port images the prompt links to, and relabels the links.

    The link is only how the images are named on the way here: it is private to Port, so the agent gets "[Image 1: ...]"
    in the text and the image itself after it. An image that can't be attached never fails the run: it is reported.
    """
    found = find_port_images(prompt)
    if not found:
        return PromptImages(prompt)
    to_load = found[:MAX_PROMPT_IMAGES]
    results = await _fetch_images([image.file_key for image in to_load])
    blocks: list[ImageContent] = []
    attached: set[str] = set()
    failed = [image.url for image in found[MAX_PROMPT_IMAGES:]]
    for number, (image, result) in enumerate(zip(to_load, results), start=1):
        if isinstance(result, BaseException):
            reason = (
                f"HTTP {result.response.status_code}"
                if isinstance(result, httpx.HTTPStatusError)
                else repr(result)
            )
            logger.warning(f"Could not load the prompt image {image.url}: {reason}")
            failed.append(image.url)
        else:
            blocks.append(
                BetaManagedAgentsTextBlockParam(type="text", text=f"Image {number}:")
            )
            blocks.append(result)
            attached.add(image.url)
    return PromptImages(_relabel(prompt, found, attached), blocks, failed)
