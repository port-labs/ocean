import logging

import requests

logger = logging.getLogger(__name__)


class PortClient:
    def __init__(self, client_id, client_secret, base_url, user_agent):
        self.api_url = base_url
        self.access_token = self.get_token(client_id, client_secret)
        self.headers = {
            'Authorization': f'Bearer {self.access_token}', 'User-Agent': user_agent}

    def get_token(self, client_id, client_secret):
        logger.info(f"Get access token for client: {client_id}")

        credentials = {'clientId': client_id, 'clientSecret': client_secret}
        token_response = requests.post(
            f'{self.api_url}/auth/access_token', json=credentials)
        token_response.raise_for_status()
        return token_response.json()['accessToken']

    def upsert_entity(self, entity):
        logger.info(
            f"Upsert entity: {entity.get('identifier')} of blueprint: {entity.get('blueprint')}")

        blueprint_id = entity.pop('blueprint')
        logger.info(
            f"Upsert entity: {entity.get('identifier')} of blueprint: {blueprint_id}")
        response = requests.post(f'{self.api_url}/blueprints/{blueprint_id}/entities', json=entity,
                                 headers=self.headers,
                                 params={'upsert': 'true', 'merge': 'true'})

        if response.status_code > 299:
            logger.error(
                f"Error upserting entity: {entity.get('identifier')} of blueprint: {blueprint_id}")
            logger.error(response.json())
            response.raise_for_status()

    def delete_entity(self, entity):
        logger.info(
            f"Delete entity: {entity.get('identifier')} of blueprint: {entity.get('blueprint')}")

        blueprint_id = entity.pop('blueprint')
        entity_id = entity.pop('identifier')
        logger.info(f"Delete entity: {entity_id} of blueprint: {blueprint_id}")
        requests.delete(f'{self.api_url}/blueprints/{blueprint_id}/entities/{entity_id}',
                        headers=self.headers,
                        params={'delete_dependents': 'true'}).raise_for_status()

    def search_entities(self, query):
        logger.info(f"Search entities by query: {query}")

        search_req = requests.post(f"{self.api_url}/entities/search", json=query, headers=self.headers,
                                   params={'exclude_calculated_properties': 'true',
                                           'include': ['blueprint', 'identifier']})
        search_req.raise_for_status()
        return search_req.json()['entities']

    def get_kafka_creds(self):
        logger.info(f"Get kafka credentials")

        creds = requests.get(
            f"{self.api_url}/kafka-credentials", headers=self.headers)
        creds.raise_for_status()

        return creds.json()

    def get_org_id(self):
        logger.info(f"Get organization id")

        org_id = requests.get(
            f"{self.api_url}/organization", headers=self.headers)
        org_id.raise_for_status()

        return org_id.json()["organization"]['id']

    def initiate_integration(self, id: str, type: str, changelog_destination: dict = None):
        logger.info(f"Initiate integration with id: {id}")

        installation = requests.post(f"{self.api_url}/integration", headers=self.headers, json={
            "installationId": id, "installationAppType": type, "changelogDestination": changelog_destination})

        if installation.status_code == 409:
            logger.info(
                f"Integration with id: {id} already exists, skipping registration")

            return
        installation.raise_for_status()

        return installation.json()
