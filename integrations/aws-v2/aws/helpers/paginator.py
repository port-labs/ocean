from __future__ import annotations

from collections import deque
from typing import Any, AsyncGenerator, List, Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from aioboto3 import AioBaseClient


class AsyncPaginator:
    """
    A helper class to asynchronously paginate API results and batch them.

    This class abstracts the logic for using an AWS-style paginator (or similar)
    with asynchronous iteration. It merges default pagination arguments provided
    at instantiation with any overrides supplied at method calls. The fetched resources
    are buffered and yielded in batches.

    Attributes:
        client (AioBaseClient): The asynchronous client used to access the API.
        method_name (str): The name of the API method for which to obtain a paginator.
        list_param (str): The key used to extract the list of resources from each API page.
        aws_paginator_kwargs (dict[str, Any]): Default keyword arguments used for pagination.
    """

    _RESYNC_BATCH_SIZE = 100
    __slots__ = ("client", "method_name", "list_param", "aws_paginator_kwargs")

    def __init__(
        self,
        client: "AioBaseClient",
        method_name: str,
        list_param: str,
        **aws_paginator_kwargs: Any,
    ):
        """
        Initializes the AsyncPaginator with the necessary client, method, and pagination parameters.

        Args:
            client (AioBaseClient): The asynchronous API client.
            method_name (str): The API method name for pagination.
            list_param (str): The key to retrieve the list of resources from the paginated response.
            **aws_paginator_kwargs (Any): Additional keyword arguments for the AWS paginator.
        """
        self.client = client
        self.method_name = method_name
        self.list_param = list_param
        self.aws_paginator_kwargs = aws_paginator_kwargs

    @property
    def service_name(self) -> str:
        """
        Retrieves the AWS client name for logging purposes.
        """
        try:
            return self.client.meta.service_model.service_name
        except AttributeError:
            return self.client.__class__.__name__

    @property
    def region_name(self) -> str:
        """
        Retrieves the AWS region for the client for logging purposes.
        """
        try:
            return self.client.meta.region_name
        except AttributeError:
            return "unknown"

    @property
    def account_id(self) -> str:
        """
        Retrieves the AWS account ID for the client for logging purposes.
        """
        try:
            return self.client.meta.account_id
        except AttributeError:
            return "unknown"

    async def _paginate_aws_resource(
        self, **kwargs: Any
    ) -> AsyncGenerator[List[Any], None]:
        """
        Asynchronously iterates over API pages.

        Pagination is handled by the AWS SDK.
        Page or batch size may be inconsistent accross different resources and control via kwargs may not be obeyed.

        Do not use this method directly. Use the `paginate` method instead.

        This method merges the instance's default pagination keyword arguments with any
        additional keyword arguments provided to the call. It then iterates over each page
        from the paginator and yields the list of resources found under the key specified by
        'list_param'.

        Args:
            **kwargs (Any): Additional keyword arguments to override default pagination parameters.

        Yields:
            List[Any]: A list of resources extracted from each page.
        """
        paginator = self.client.get_paginator(self.method_name)
        paginator_args = {**self.aws_paginator_kwargs, **kwargs}
        page_count = 1
        async for page in paginator.paginate(**paginator_args):
            resources = page.get(self.list_param, [])
            logger.debug(
                f"Queried {len(resources)} resources from {self.service_name} in {self.region_name} in page {page_count}"
            )
            yield resources
            page_count += 1

    async def paginate(
        self, *, batch_size: Optional[int] = None, **kwargs: Any
    ) -> AsyncGenerator[List[Any], None]:
        """
        Guarantees that resources are paginated with consistent batch sizes.

        Items are buffered in a queue to avoid repeated list slicing. When the buffer's size
        reaches the batch_size, a batch is yielded and the buffer is reduced. The final batch,
        which may be smaller than batch_size, is yielded once all pages have been processed.

        Args:
            batch_size (Optional[int]): The maximum number of resources per yielded batch.
                Defaults to _RESYNC_BATCH_SIZE if not provided.
            **kwargs (Any): Additional keyword arguments to pass to the aws paginator method.

        Yields:
            List[Any]: A batch (list) of resources aggregated from the paginated results.
        """
        batch_size = batch_size or self._RESYNC_BATCH_SIZE
        buffer: deque[Any] = deque()
        page_count = 1

        async for resources in self._paginate_aws_resource(**kwargs):
            resources_processed_in_full_batch = 0
            buffer.extend(resources)
            while len(buffer) >= batch_size:
                resources_processed_in_full_batch += batch_size
                batch = [buffer.popleft() for _ in range(batch_size)]
                logger.debug(
                    f"Buffering {resources_processed_in_full_batch}/{len(resources)} queried {self.service_name} resources fetched from page {page_count} for account {self.account_id} in {self.region_name}"
                )
                yield batch
            page_count += 1
        if buffer:
            final_batch = list(buffer)
            logger.debug(
                f"Buffering the final {len(final_batch)} queried {self.service_name} resources fetched from page {page_count} for account {self.account_id} in {self.region_name}"
            )
            yield final_batch
