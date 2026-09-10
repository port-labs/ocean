from port_ocean.context.ocean import ocean

from webhook_processors.constants import WEBHOOK_PATH
from webhook_processors.fake_person_webhook_processor import (
    FakePersonWebhookProcessor,
)


def register_webhook_processors() -> None:
    ocean.add_webhook_processor(WEBHOOK_PATH, FakePersonWebhookProcessor)
