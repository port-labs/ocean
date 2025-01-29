import asyncio

from .abstract_webhook_processor import AbstractWebhookProcessor


async def process_webhook_request(processor: AbstractWebhookProcessor) -> None:
    """Process a webhook request with retry logic.

    Args:
        processor: The webhook processor to use
    """
    await processor.before_processing()

    payload = processor.event.payload
    headers = processor.event.headers

    if not await processor.authenticate(payload, headers):
        raise ValueError("Authentication failed")

    if not await processor.validate_payload(payload):
        raise ValueError("Invalid payload")

    while True:
        try:
            await processor.handle_event(payload)
            break

        except Exception as e:
            await processor.on_error(e)

            if (
                processor.should_retry(e)
                and processor.retry_count < processor.max_retries
            ):
                processor.retry_count += 1
                delay = processor.calculate_retry_delay()
                await asyncio.sleep(delay)
                continue

            raise

    await processor.after_processing()
