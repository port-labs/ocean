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
_URL = r"https?://[^\s)\]\"'<>]+/organizations/[^/\s)\]\"'<>]+/markdown_image/[\w%-]+(?:\.[\w%-]+)*"
# A markdown image, or a bare link.
_IMAGE_LINK = re.compile(rf"!\[(?P<alt>[^\]]*)\]\((?P<md>{_URL})\)|(?P<bare>{_URL})")

MAX_PROMPT_IMAGES = 10
# Anthropic takes images of up to 5 MB, as base64: 3.75 MB of image.
MAX_IMAGE_BYTES = 5 * 1024 * 1024 * 3 // 4
SUPPORTED_MEDIA_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)
_FETCH_TIMEOUT_SECONDS = 30.0

ImageContent = BetaManagedAgentsTextBlockParam | BetaManagedAgentsImageBlockParam


@dataclass(frozen=True)
class PortImage:
    url: str
    alt: str


@dataclass(frozen=True)
class PromptImages:
    """A prompt whose Port image links read as labels, and the images those labels name.

    `blocks` follow the prompt in the message: a text block "Image N:" and the image, for each image that was loaded.
    `failed` are the links of the images that could not be loaded.
    """

    prompt: str
    blocks: list[ImageContent] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def find_port_images(prompt: str) -> list[PortImage]:
    """The distinct Port images the prompt links to, in order of appearance, up to the limit."""
    images: dict[str, PortImage] = {}
    for match in _IMAGE_LINK.finditer(prompt):
        url = match.group("md") or match.group("bare")
        alt = " ".join((match.group("alt") or "").split())
        if url not in images and len(images) < MAX_PROMPT_IMAGES:
            images[url] = PortImage(url, alt)
    return list(images.values())


def _label(number: int, alt: str, loaded: bool) -> str:
    text = f"Image {number}: {alt}" if alt else f"Image {number}"
    return f"[{text}]" if loaded else f"[{text} - could not be loaded]"


def _file_key(url: str) -> str:
    return unquote(urlparse(url).path).lstrip("/")


async def _fetch_image(url: str) -> BetaManagedAgentsImageBlockParam:
    """The image as a base64 content block. Port reads the organization from the token, so only its images come back."""
    port_client = ocean.port_client
    response = await port_client.client.get(
        f"{port_client.auth.api_url}/asset/content",
        params={"fileKey": _file_key(url), "maxSizeBytes": MAX_IMAGE_BYTES},
        headers=await port_client.auth.headers(),
        timeout=_FETCH_TIMEOUT_SECONDS,
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


async def load_prompt_images(prompt: str) -> PromptImages:
    """Loads the Port images the prompt links to, and relabels the links.

    The link is only how the images are named on the way here: it is private to Port, so the agent gets "[Image 1: ...]"
    in the text and the image itself after it. An image that can't be loaded never fails the run: it is reported.
    """
    found = find_port_images(prompt)
    if not found:
        return PromptImages(prompt)
    results = await asyncio.gather(
        *(_fetch_image(image.url) for image in found), return_exceptions=True
    )
    blocks: list[ImageContent] = []
    failed: list[str] = []
    labels: dict[str, str] = {}
    for number, (image, result) in enumerate(zip(found, results), start=1):
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
        labels[image.url] = _label(
            number, image.alt, loaded=not isinstance(result, BaseException)
        )

    def relabel(match: re.Match[str]) -> str:
        return labels.get(match.group("md") or match.group("bare"), match.group(0))

    return PromptImages(_IMAGE_LINK.sub(relabel, prompt), blocks, failed)
