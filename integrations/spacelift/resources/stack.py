# from port_ocean.resources import Resource
from port_ocean.models.resource import Resource

class SpaceliftStack(Resource):
    kind = "spacelift-stack"
    title = "name"
    properties = {
        "name": {"type": "string", "title": "Name"},
        "description": {"type": "string", "title": "Description"},
    }