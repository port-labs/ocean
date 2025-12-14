from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException
import httpx

from port_ocean.context.ocean import ocean

from fake_org_data.generator import (
    generate_fake_codeowners_file,
    generate_fake_json_file,
    generate_fake_webhook_event,
    generate_fake_yaml_file,
    generate_fake_persons,
    generate_fake_repositories,
)
from fake_org_data.markdown_generator import generate_fake_readme_file

FAKE_PERSONS = "/fake-employees"
FAKE_DEPARTMENTS = "/fake-departments"
FAKE_REPOSITORIES = "/fake-repositories"
FAKE_WEBHOOK = "/fake-webhook"

FAKE_FILE = "/fake-file/{file_path}"

OCEAN_WEBHOOK_URL = "http://127.0.0.1:8000/integration/webhook"


def get_fake_router() -> APIRouter:
    if __name__ == "__main__":
        return APIRouter(prefix="/fake-integration")
    else:
        return ocean.router


def initialize_fake_routes() -> None:
    router = get_fake_router()

    @router.get(FAKE_FILE)
    async def get_fake_file(
        file_path: str,
        file_size_kb: int = -1,
        latency: int = -1,
        row_count: int = -1,
        entity_amount: int = -1,
        entity_kb_size: int = -1,
        items_to_parse_entity_count: int = -1,
        items_to_parse_entity_size_kb: int = -1,
    ) -> Dict[str, Any]:
        suffix = file_path.split(".")[-1]
        if suffix == "md":
            file_content = await generate_fake_readme_file(file_size_kb, latency)
        elif suffix == "txt":
            file_content = await generate_fake_codeowners_file(row_count, latency)
        elif suffix == "yml":
            file_content = await generate_fake_yaml_file(
                entity_amount,
                entity_kb_size,
                latency,
                items_to_parse_entity_count,
                items_to_parse_entity_size_kb,
            )
        elif suffix == "json":
            file_content = await generate_fake_json_file(
                entity_amount,
                entity_kb_size,
                latency,
                items_to_parse_entity_count,
                items_to_parse_entity_size_kb,
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Invalid file suffix: {suffix}"
            )
        return {"filename": file_path, "content": file_content}

    @router.get(FAKE_PERSONS)
    async def get_persons(
        entity_amount: int = -1,
        entity_kb_size: int = -1,
        latency: int = -1,
        items_to_parse_entity_count: int = -1,
        items_to_parse_entity_size_kb: int = -1,
    ) -> Dict[str, Any]:
        """Get Employees per Department

        Since we grab these numbers from the config,
        we need a way to set the variables and use the default,
        since the config validation will fail for an empty value,
        we add -1 as the default


        """
        result = await generate_fake_persons(
            entity_amount,
            entity_kb_size,
            latency,
            items_to_parse_entity_count,
            items_to_parse_entity_size_kb,
        )
        return {"results": result}

    @router.get(FAKE_REPOSITORIES)
    async def get_repositories(
        entity_amount: int = -1,
        entity_kb_size: int = -1,
        latency: int = -1,
    ) -> Dict[str, Any]:
        """Get Fake Repositories

        Since we grab these numbers from the config,
        we need a way to set the variables and use the default,
        since the config validation will fail for an empty value,
        we add -1 as the default
        """
        result = await generate_fake_repositories(
            entity_amount, entity_kb_size, latency
        )
        return {"results": result}

    USER_AGENT = "Fake-Generator/1.0"

    async def send_fake_webhook_event(
        entity_amount: int,
        entity_kb_size: int,
        latency: int,
        items_to_parse_entity_count: int,
        items_to_parse_entity_size_kb: int,
        webhook_action: Literal["create", "update", "delete"],
    ) -> Dict[str, Any]:
        url = OCEAN_WEBHOOK_URL
        fake_event = await generate_fake_webhook_event(
            "fake-repository",
            entity_amount,
            entity_kb_size,
            latency,
            items_to_parse_entity_count,
            items_to_parse_entity_size_kb,
            webhook_action,
        )
        response = await httpx.AsyncClient().post(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
            json=fake_event,
        )
        response.raise_for_status()
        return fake_event

    @router.post(FAKE_WEBHOOK)
    async def invoke_webhook(
        entity_amount: int = -1,
        entity_kb_size: int = -1,
        latency: int = -1,
        items_to_parse_entity_count: int = -1,
        items_to_parse_entity_size_kb: int = -1,
        webhook_action: Literal["create", "update", "delete"] = "create",
    ) -> Dict[str, Any]:
        """Invoke Fake Webhook"""
        result = await send_fake_webhook_event(
            entity_amount,
            entity_kb_size,
            latency,
            items_to_parse_entity_count,
            items_to_parse_entity_size_kb,
            webhook_action,
        )
        return {"results": result}

    return router


if __name__ == "__main__":
    from fastapi import FastAPI
    import uvicorn

    app = FastAPI()
    app.include_router(initialize_fake_routes())
    uvicorn.run(app, host="0.0.0.0", port=9000)
