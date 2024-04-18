
from gcp_core.search.searches import get_single_folder, get_single_organization, get_single_project, get_single_topic, search_single_resource
from gcp_core.utils import EXTRA_PROJECT_FIELD, AssetTypesWithSpecialHandling
from port_ocean.core.ocean_types import RAW_ITEM


async def feed_event_to_resource(
    asset_type: str, asset_name: str, project_id: str
) -> RAW_ITEM:
    resource = None
    match asset_type:  
        case AssetTypesWithSpecialHandling.TOPIC:  
            resource = await get_single_topic(asset_name)  
            resource[EXTRA_PROJECT_FIELD] = await get_single_project(project_id)  
        case AssetTypesWithSpecialHandling.FOLDER:  
            resource = await get_single_folder(asset_name)  
        case AssetTypesWithSpecialHandling.ORGANIZATION:  
            resource = await get_single_organization(asset_name)  
        case AssetTypesWithSpecialHandling.PROJECT:  
            resource = await get_single_project(asset_name)  
        case _:  
            resource = await search_single_resource(project_id, asset_type, asset_name)  
    return resource
