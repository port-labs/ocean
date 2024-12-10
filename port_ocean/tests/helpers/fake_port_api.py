import uvicorn
import os
from typing import Dict, Any
from fastapi import FastAPI, Request

SMOKE_TEST_SUFFIX = os.environ.get("SMOKE_TEST_SUFFIX", "smoke")

app = FastAPI()

FAKE_DEPARTMENT_BLUEPRINT = {
    "identifier": f"fake-department-{SMOKE_TEST_SUFFIX}",
    "title": "Fake Department",
    "icon": "Blueprint",
    "schema": {"properties": {"name": {"type": "string"}, "id": {"type": "string"}}},
    "relations": {},
}
FAKE_PERSON_BLUEPRINT = {
    "identifier": f"fake-person-{SMOKE_TEST_SUFFIX}",
    "title": "Fake Person",
    "icon": "Blueprint",
    "schema": {
        "properties": {
            "status": {
                "type": "string",
                "enum": ["WORKING", "NOPE"],
                "enumColors": {"WORKING": "green", "NOPE": "red"},
                "title": "Status",
            },
            "email": {"type": "string", "format": "email", "title": "Email"},
            "age": {"type": "number", "title": "Age"},
            "bio": {"type": "string", "title": "Bio"},
        }
    },
    "relations": {
        "department": {
            "title": "Department",
            "description": "Fake Department",
            "target": f"fake-department-{SMOKE_TEST_SUFFIX}",
            "required": False,
            "many": False,
        }
    },
}


@app.router.get("/v1/blueprints/{blueprint_id}")
@app.router.patch("/v1/blueprints/{blueprint_id}")
async def get_blueprint(blueprint_id: str) -> Dict[str, Any]:
    return {
        "blueprint": (
            FAKE_PERSON_BLUEPRINT
            if blueprint_id.startswith("fake-person")
            else FAKE_DEPARTMENT_BLUEPRINT
        )
    }


@app.router.post("/v1/entities/search")
async def search_entities() -> Dict[str, Any]:
    return {"ok": True, "entities": []}


@app.router.get("/v1/integration/{integration_id}")
@app.router.patch("/v1/integration/{integration_id}")
@app.router.patch("/v1/integration/{integration_id}/resync-state")
async def get_integration(integration_id: str) -> Dict[str, Any]:
    return {
        "integration": {
            "identifer": integration_id,
            "resyncState": {
                "status": "completed",
                "lastResyncEnd": "2024-11-20T12:01:54.225362+00:00",
                "lastResyncStart": "2024-11-20T12:01:45.483844+00:00",
                "nextResync": None,
                "intervalInMinuets": None,
                "updatedAt": "2024-11-20T12:01:54.355Z",
            },
            "config": {
                "deleteDependentEntities": True,
                "createMissingRelatedEntities": True,
                "enableMergeEntity": True,
                "resources": [
                    {
                        "kind": "fake-department",
                        "selector": {"query": "true"},
                        "port": {
                            "entity": {
                                "mappings": {
                                    "identifier": ".id",
                                    "title": ".name",
                                    "blueprint": f'"fake-department-{SMOKE_TEST_SUFFIX}"',
                                    "properties": {"name": ".name", "id": ".id"},
                                }
                            }
                        },
                    },
                    {
                        "kind": "fake-person",
                        "selector": {"query": "true"},
                        "port": {
                            "entity": {
                                "mappings": {
                                    "identifier": ".id",
                                    "title": ".name",
                                    "blueprint": f'"fake-person-{SMOKE_TEST_SUFFIX}"',
                                    "properties": {
                                        "name": ".name",
                                        "email": ".email",
                                        "status": ".status",
                                        "age": ".age",
                                        "department": ".department.name",
                                    },
                                    "relations": {"department": ".department.id"},
                                }
                            }
                        },
                    },
                ],
            },
            "installationType": "OnPrem",
            "_orgId": "org_ZOMGMYUNIQUEID",
            "_id": "integration_0dOOhnlJQDjMPnfe",
            "identifier": f"smoke-test-integration-{SMOKE_TEST_SUFFIX}",
            "integrationType": "smoke-test",
            "createdBy": "APSQAYsYoIwPXqjn6XpwCAgnPakkNO67",
            "updatedBy": "APSQAYsYoIwPXqjn6XpwCAgnPakkNO67",
            "createdAt": "2024-11-20T12:01:42.651Z",
            "updatedAt": "2024-11-20T12:01:54.355Z",
            "clientId": "",
            "logAttributes": {
                "ingestId": "DOHSAIDHOMER",
                "ingestUrl": "http://localhost:5555/logs/integration/DOHSAIDHOMER",
            },
        },
    }


@app.router.post("/v1/blueprints/{blueprint_id}/entities")
async def upsert_entities(blueprint_id: str, request: Request) -> Dict[str, Any]:
    json = await request.json()

    return {
        "ok": True,
        "entity": json,
    }


@app.router.post("/v1/auth/access_token")
async def auth_token() -> Dict[str, Any]:
    return {
        "accessToken": "ZOMG",
        "expiresIn": 1232131231,
        "tokenType": "adadad",
    }


@app.router.delete("/v1/blueprints/{blueprint_id}/all-entities")
async def delete_blueprint(blueprint_id: str, request: Request) -> Dict[str, Any]:
    return {"migrationId": "ZOMG"}


@app.router.get("/v1/migrations/{migration_id}")
async def migration(migration_id: str, request: Request) -> Dict[str, Any]:
    return {
        "migration": {
            "id": migration_id,
            "status": "COMPLETE",
            "actor": "Dwayne Scissors Johnson",
            "sourceBlueprint": "leBlue",
            "mapping": {},
        }
    }


CATCH_ALL = "/{full_path:path}"


@app.router.get(CATCH_ALL)
@app.router.post(CATCH_ALL)
@app.router.patch(CATCH_ALL)
@app.router.delete(CATCH_ALL)
async def catch_all(full_path: str, request: Request) -> str:
    return f"Hello there from fake Port API - {full_path}, thanks for accessing me with {request.method}"


def start() -> None:
    uvicorn.run(app, host="0.0.0.0", port=5555)


if __name__ == "__main__":
    start()
