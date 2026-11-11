import asyncio
import time
from datetime import datetime, timedelta, timezone
import inspect
import typing
from typing import Callable, Awaitable, Any, cast
import uuid
import httpx
import json
from loguru import logger
from port_ocean.clients.dsp.lifecycle import GranularityType, SyncType
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import TriggerType, event_context, EventType, event
from port_ocean.context.metric_resource import metric_resource_context
from port_ocean.context.ocean import ocean
from port_ocean.context.resource import resource_context
from port_ocean.context import resource
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.integrations.mixins import HandlerMixin, EventsMixin
from port_ocean.core.integrations.mixins.lakehouse_buffer import LakehouseBuffer
from port_ocean.core.integrations.mixins.utils import (
    build_lakehouse_data_entry,
    build_live_event_data_entry,
    selector_hash_from_resource,
    send_raw_live_event,
    start_kind_tracking,
    stop_kind_tracking,
    unsupported_kind_response,
    resync_generator_wrapper,
    resync_function_wrapper,
)
from port_ocean.core.models import (
    LakehouseDataEntryMetadata,
    LakehouseEventType,
    LakehouseOperation,
)
from port_ocean.core.ocean_types import (
    RAW_RESULT,
    RESYNC_RESULT,
    ASYNC_GENERATOR_RESYNC_TYPE,
    RAW_ITEM,
    ETLPhase,
)
from port_ocean.core.utils.utils import gather_and_split_errors_from_results
from port_ocean.core.incremental.cursor_context import with_active_incremental_cursor
from port_ocean.core.incremental.cursor_store import CursorStore
from port_ocean.exceptions.core import (
    OceanAbortException,
)
from port_ocean.helpers.metric.metric import (
    MetricResourceKind,
    SyncState,
    MetricType,
    MetricPhase,
)
from port_ocean.helpers.metric.utils import TimeMetric
from port_ocean.helpers.monitor.monitor import start_monitoring, stop_monitoring

SEND_RAW_DATA_EXAMPLES_AMOUNT = 5
LIFECYCLE_ABORT_POLL_INTERVAL_SECONDS = 10

KindResult = tuple[int, list[Exception]]


class SyncRawMixin(HandlerMixin, EventsMixin):
    """Mixin class for synchronization of raw data.

    This mixin class extends the functionality of HandlerMixin and EventsMixin to provide methods for
    extracting raw data and handing it to the data-source-processor, which maps it to entities,
    upserts them and reconciles stale entities.

    Note:
        Raw entities are entities with a more primitive structure, usually fetched directly from a resource.
    """

    def __init__(self) -> None:
        HandlerMixin.__init__(self)
        EventsMixin.__init__(self)

    async def _on_resync(self, kind: str) -> RAW_RESULT:
        raise NotImplementedError("on_resync must be implemented")

    async def _get_resource_raw_results(
        self,
        resource_config: ResourceConfig,
        send_raw_data_examples_amount: int = 0,
    ) -> tuple[RESYNC_RESULT, list[Exception]]:
        logger.info(f"Fetching {resource_config.kind} resync results")

        is_incremental = event.event_type == EventType.INCREMENTAL_RESYNC
        event_mapping = (
            self.event_strategy.incremental
            if is_incremental
            else self.event_strategy.resync
        )

        if not (
            event_mapping.get(resource_config.kind) or event_mapping.get(None)
        ):
            return unsupported_kind_response(
                resource_config.kind,
                cast(list[str], list(event_mapping.keys())),
            )

        fns = self._collect_resync_functions(resource_config, event_mapping)
        logger.info(f"Found {len(fns)} resync functions for {resource_config.kind}")

        results, errors = await self._execute_resync_tasks(
            fns, resource_config, send_raw_data_examples_amount
        )

        return results, errors

    def _collect_resync_functions(
        self,
        resource_config: ResourceConfig,
        event_mapping: dict[str | None, list[Callable[[str], Awaitable[RAW_RESULT]]]],
    ) -> list[Callable[[str], Awaitable[RAW_RESULT]]]:
        fns = [
            *event_mapping[resource_config.kind],
            *event_mapping[None],
        ]

        if self.__class__._on_resync != SyncRawMixin._on_resync:
            fns.append(self._on_resync)

        return fns

    async def _execute_resync_tasks(
        self,
        fns: list[Callable[[str], Awaitable[RAW_RESULT]]],
        resource_config: ResourceConfig,
        send_raw_data_examples_amount: int = 0,
    ) -> tuple[RESYNC_RESULT, list[RAW_RESULT | Exception]]:
        tasks = []
        results = []
        for task in fns:
            if inspect.isasyncgenfunction(task):
                logger.info(
                    f"Found async generator function for {resource_config.kind} name: {task.__qualname__}"
                )
                results.append(
                    resync_generator_wrapper(
                        task,
                        resource_config.kind,
                        send_raw_data_examples_amount=send_raw_data_examples_amount,
                    )
                )
            else:
                logger.info(
                    f"Found sync function for {resource_config.kind} name: {task.__qualname__}"
                )
                task = typing.cast(Callable[[str], Awaitable[RAW_RESULT]], task)
                tasks.append(
                    resync_function_wrapper(
                        task,
                        resource_config.kind,
                        send_raw_data_examples_amount=send_raw_data_examples_amount,
                    )
                )

        logger.info(
            f"Found {len(tasks) + len(results)} resync tasks for {resource_config.kind}"
        )
        successful_results, errors = await gather_and_split_errors_from_results(tasks)
        results.extend(
            sum(
                successful_results,
                [],
            )
        )

        logger.info(
            f"Triggered {len(tasks)} tasks for {resource_config.kind}, failed: {len(errors)}"
        )

        return results, errors

    async def _buffer_raw_items(
        self,
        buffer: LakehouseBuffer,
        resource_config: ResourceConfig,
        index: int,
        items: list[RAW_ITEM],
    ) -> None:
        await buffer.add(
            build_lakehouse_data_entry(
                items=items,
                metadata=LakehouseDataEntryMetadata(
                    operation=LakehouseOperation.UPSERT,
                    resource_index=index,
                    extraction_timestamp=int(datetime.now().timestamp() * 1000),
                    selector_hash=selector_hash_from_resource(resource_config),
                ),
                export_env_variables=resource_config.selector.export_env_variables,
            )
        )

    @TimeMetric(MetricPhase.RESYNC)
    async def _register_in_batches(
        self,
        resource_config: ResourceConfig,
        index: int,
    ) -> KindResult:
        send_raw_data_examples_amount = (
            SEND_RAW_DATA_EXAMPLES_AMOUNT if ocean.config.send_raw_data_examples else 0
        )

        with logger.contextualize(etl_phase=ETLPhase.EXTRACT):
            logger.info("Starting extract phase")
            results, errors = await self._get_resource_raw_results(
                resource_config, send_raw_data_examples_amount
            )
            async_generators: list[ASYNC_GENERATOR_RESYNC_TYPE] = []
            raw_results: RAW_RESULT = []

            for result in results:
                if isinstance(result, dict):
                    raw_results.append(result)
                else:
                    async_generators.append(result)

            buffer = LakehouseBuffer(
                sync_id=event.id,
                kind=resource_config.kind,
                resync_start_time=event.attributes.get("resync_start_time"),
                event_type=LakehouseEventType.RESYNC,
                flush_interval_seconds=ocean.config.lakehouse_buffer_interval_seconds,
                max_buffer_count=ocean.config.lakehouse_buffer_max_count,
            )

            logger.info(
                "Extract phase complete",
                raw_items=len(raw_results),
                async_generators=len(async_generators),
            )

        number_of_raw_results = 0

        if raw_results:
            await self._buffer_raw_items(buffer, resource_config, index, raw_results)
            number_of_raw_results += len(raw_results)

        for generator in async_generators:
            try:
                async for items in generator:
                    await self._buffer_raw_items(buffer, resource_config, index, items)
                    number_of_raw_results += len(items)
            except* OceanAbortException as error:
                ocean.metrics.sync_state = SyncState.FAILED
                errors.append(error)

        await buffer.flush()

        logger.info(
            f"Finished extracting kind: {resource_config.kind}-{resource.resource.index}, {number_of_raw_results} raw results handed to the data-source-processor"
        )

        ocean.metrics.set_metric(
            name=MetricType.SUCCESS_NAME,
            labels=[ocean.metrics.current_resource_kind(), MetricPhase.RESYNC],
            value=int(not errors),
        )

        ocean.metrics.inc_metric(
            name=MetricType.OBJECT_COUNT_NAME,
            labels=[
                ocean.metrics.current_resource_kind(),
                MetricPhase.EXTRACT,
                MetricPhase.ExtractResult.EXTRACTED,
            ],
            value=number_of_raw_results,
        )

        return number_of_raw_results, errors

    async def _send_raw_live_event(
        self,
        kind: str,
        results: list[dict[Any, Any]],
        operation: LakehouseOperation,
    ) -> None:
        config = await self.port_app_config_handler.get_port_app_config()
        resources = [
            (index, resource_config)
            for index, resource_config in enumerate(config.resources)
            if resource_config.kind == kind
        ]
        if not resources or not results:
            return

        data_entries = []
        for index, resource_config in resources:
            data_entries.append(
                build_live_event_data_entry(
                    resource=resource_config,
                    resource_index=index,
                    items=results,
                    operation=operation,
                )
            )

        await send_raw_live_event(
            event_id=str(uuid.uuid4()),
            kind=kind,
            resync_start_time=datetime.now(timezone.utc),
            data_entries=data_entries,
        )

    async def register_raw(
        self,
        kind: str,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
    ) -> None:
        """Hand raw items of a kind to the data-source-processor to be mapped and upserted.

        Args:
            kind (str): The kind of the raw items.
            results (list[dict[Any, Any]]): The raw items.
            user_agent_type (UserAgentType): The type of user agent.
        """
        logger.info(f"Registering raw state for {kind}", items=len(results))
        await self._send_raw_live_event(kind, results, LakehouseOperation.UPSERT)

    async def unregister_raw(
        self,
        kind: str,
        results: list[dict[Any, Any]],
        user_agent_type: UserAgentType,
    ) -> None:
        """Hand raw items of a kind to the data-source-processor to be mapped and deleted.

        Args:
            kind (str): The kind of the raw items.
            results (list[dict[Any, Any]]): The raw items.
            user_agent_type (UserAgentType): The type of user agent.
        """
        logger.info(f"Unregistering raw state for {kind}", items=len(results))
        await self._send_raw_live_event(kind, results, LakehouseOperation.DELETE)

    async def _process_resource(
        self,
        resource: ResourceConfig,
        index: int,
    ) -> KindResult:
        # create resource context per resource kind, so resync method could have access to the resource
        # config as we might have multiple resources in the same event
        async with resource_context(resource, index):
            await start_monitoring()
            resource_kind_id = f"{resource.kind}-{index}"
            ocean.metrics.sync_state = SyncState.SYNCING

            # Start monitoring resource usage for this kind
            start_kind_tracking(resource_kind_id)

            resync_id = ocean.metrics.event_id
            if resync_id:
                await ocean.app.lifecycle_client.notify_started(
                    event_id=resync_id,
                    integration_id=ocean.config.integration.identifier,
                    integration_type=ocean.config.integration.type,
                    granularity=GranularityType.KIND,
                    kind_identifier=resource_kind_id,
                )

            task = asyncio.create_task(self._register_in_batches(resource, index))
            event.on_abort(lambda: task.cancel())

            kind_results: KindResult = (0, [])
            try:
                kind_results = await task
                if ocean.metrics.sync_state != SyncState.FAILED:
                    ocean.metrics.sync_state = SyncState.COMPLETED
            except asyncio.CancelledError:
                if event.external_abort:
                    raise
                logger.warning(f"Resource {resource.kind} processing was aborted")
                ocean.metrics.sync_state = SyncState.ABORTED
                if resync_id:
                    await ocean.app.lifecycle_client.notify_aborted(
                        event_id=resync_id,
                        granularity=GranularityType.KIND,
                        kind_identifier=resource_kind_id,
                    )
                raise
            except Exception as e:
                logger.error(
                    f"Resource {resource.kind} processing failed unexpectedly: {e}"
                )
                ocean.metrics.sync_state = SyncState.FAILED
                kind_results = (0, [e])
            finally:
                # Stop tracking and report resource usage metrics
                stop_kind_tracking(resource_kind_id)
                await stop_monitoring()

            if event.event_type != EventType.INCREMENTAL_RESYNC:
                await ocean.metrics.send_metrics_to_webhook(kind=resource_kind_id)

            if resync_id:
                if ocean.metrics.sync_state == SyncState.FAILED:
                    await ocean.app.lifecycle_client.notify_failed(
                        event_id=resync_id,
                        granularity=GranularityType.KIND,
                        kind_identifier=resource_kind_id,
                    )
                else:
                    await ocean.app.lifecycle_client.notify_finished(
                        event_id=resync_id,
                        integration_type=ocean.config.integration.type,
                        granularity=GranularityType.KIND,
                        kind_identifier=resource_kind_id,
                    )

            return kind_results

    async def process_resource(
        self,
        resource: ResourceConfig,
        index: int,
    ) -> KindResult:
        with logger.contextualize(resource_kind=resource.kind, index=index):
            return await self._process_resource(resource, index)

    async def _handle_resync_abortion(
        self,
        creation_results: list[KindResult],
        app_config: Any,
    ) -> None:
        """Handle resync abortion by updating metrics for runtime, pending resources, and reconciliation.

        Args:
            creation_results: Results from the kinds that have been processed so far
            app_config: The application configuration containing resource definitions
        """
        async with metric_resource_context(MetricResourceKind.RUNTIME):
            ocean.metrics.sync_state = SyncState.ABORTED
            await ocean.metrics.send_metrics_to_webhook(kind=MetricResourceKind.RUNTIME)

        for pending_index in range(len(creation_results), len(app_config.resources)):
            pending_resource = app_config.resources[pending_index]
            pending_kind_id = f"{pending_resource.kind}-{pending_index}"
            async with metric_resource_context(pending_kind_id):
                ocean.metrics.sync_state = SyncState.ABORTED
                await ocean.metrics.send_metrics_to_webhook(kind=pending_kind_id)

        async with metric_resource_context(MetricResourceKind.RECONCILIATION):
            ocean.metrics.sync_state = SyncState.ABORTED
            ocean.metrics.set_metric(
                name=MetricType.SUCCESS_NAME,
                labels=[MetricResourceKind.RECONCILIATION, MetricPhase.RESYNC],
                value=0,
            )
            await ocean.metrics.send_metrics_to_webhook(
                kind=MetricResourceKind.RECONCILIATION
            )

    async def _poll_for_lifecycle_abort(self, resync_id: str) -> None:
        while not event.aborted:
            await asyncio.sleep(LIFECYCLE_ABORT_POLL_INTERVAL_SECONDS)
            status = await ocean.app.lifecycle_client.get_resync_status(resync_id)
            if status != "aborted":
                continue
            logger.warning(
                "Lifecycle API reported aborted status; cancelling Ocean resync",
                resync_id=resync_id,
            )
            event.abort(external_abort=True)
            return

    async def _sync_incremental_kind(
        self,
        resource: ResourceConfig,
        index: int,
        cursor: datetime,
        next_cursor: datetime,
        cursor_store: CursorStore,
        integration_type: str,
        integration_id: str,
        kind_identifier: str,
    ) -> bool:
        """Sync one kind incrementally. Returns True when the cursor was advanced."""
        kind_started_at = time.monotonic()
        try:
            with with_active_incremental_cursor(cursor):
                items_fetched, errors = await self.process_resource(resource, index)

            if errors:
                ocean.metrics.set_metric(
                    name=MetricType.INCREMENTAL_KIND_DURATION_NAME,
                    labels=[integration_type, kind_identifier],
                    value=time.monotonic() - kind_started_at,
                )
                ocean.metrics.inc_metric(
                    name=MetricType.INCREMENTAL_RUN_ERRORS_TOTAL_NAME,
                    labels=[integration_type, "kind_errors"],
                    value=1,
                )
                logger.error(
                    "Incremental sync failed — cursor not updated, next run will retry",
                    integration_type=integration_type,
                    integration_id=integration_id,
                    event_id=event.id,
                    kind=resource.kind,
                    index=index,
                    error="; ".join(str(error) for error in errors),
                )
                return False

            await cursor_store.save(resource.kind, index, next_cursor)
            ocean.metrics.set_metric(
                name=MetricType.INCREMENTAL_KIND_DURATION_NAME,
                labels=[integration_type, kind_identifier],
                value=time.monotonic() - kind_started_at,
            )
            logger.info(
                "Incremental sync kind completed",
                integration_type=integration_type,
                integration_id=integration_id,
                event_id=event.id,
                kind=resource.kind,
                index=index,
                items_fetched=items_fetched,
            )
            return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ocean.metrics.set_metric(
                name=MetricType.INCREMENTAL_KIND_DURATION_NAME,
                labels=[integration_type, kind_identifier],
                value=time.monotonic() - kind_started_at,
            )
            ocean.metrics.inc_metric(
                name=MetricType.INCREMENTAL_RUN_ERRORS_TOTAL_NAME,
                labels=[integration_type, "kind_exception"],
                value=1,
            )
            logger.error(
                "Incremental sync failed — cursor not updated, next run will retry",
                integration_type=integration_type,
                integration_id=integration_id,
                event_id=event.id,
                kind=resource.kind,
                index=index,
                error=str(exc),
            )
            return False

    async def sync_incremental(
        self,
        interval_seconds: int,
        trigger_type: TriggerType = "machine",
        user_agent_type: UserAgentType = UserAgentType.exporter,
    ) -> None:
        """Run incremental sync for all kinds registered with ``on_incremental_resync``.

        Cursor semantics
        ----------------
        * ``next_cursor`` is snapshotted at the start of the run so items that
          change during the fetch window are picked up on the next run.
        * On failure the cursor is not advanced, allowing the next run to retry
          from the same starting point.
        * When no cursor exists (first run) the seed is ``now − interval_seconds``.
        """
        integration_type = ocean.config.integration.type
        integration_id = ocean.config.integration.identifier

        async with event_context(
            EventType.INCREMENTAL_RESYNC, trigger_type=trigger_type
        ):
            ocean.metrics.event_id = event.id
            logger.info(
                "Incremental resync triggered",
                integration_type=integration_type,
                integration_id=integration_id,
                event_id=event.id,
                interval_seconds=interval_seconds,
            )
            run_started_at_monotonic = time.monotonic()
            kinds_succeeded = 0
            kind_identifier: str | None = None
            kinds_total = 0
            try:
                app_config = await self.port_app_config_handler.get_port_app_config(
                    use_cache=False
                )

                incremental_resources = [
                    (index, resource_cfg)
                    for index, resource_cfg in enumerate(app_config.resources)
                    if self.event_strategy.incremental.get(resource_cfg.kind)
                ]

                if not incremental_resources:
                    logger.info(
                        "No kinds registered for incremental sync, skipping",
                        integration_type=integration_type,
                        integration_id=integration_id,
                        event_id=event.id,
                    )
                    return

                logger.info(
                    "Incremental sync kinds registered",
                    integration_type=integration_type,
                    integration_id=integration_id,
                    event_id=event.id,
                    kinds=[cfg.kind for _, cfg in incremental_resources],
                )

                cursor_store = CursorStore(ocean.port_client)
                run_started_at = datetime.now(timezone.utc)
                kinds_total = len(incremental_resources)

                await ocean.app.lifecycle_client.notify_resync_started(
                    resync_id=event.id,
                    integration_id=ocean.config.integration.identifier,
                    integration_type=ocean.config.integration.type,
                    started_at=datetime.now(timezone.utc),
                    sync_type=SyncType.INCREMENTAL_RESYNC.value,
                    kind_identifiers=[
                        f"{resource_cfg.kind}-{index}"
                        for index, resource_cfg in incremental_resources
                    ],
                )

                for index, resource_cfg in incremental_resources:
                    stored_cursor = await cursor_store.get(resource_cfg.kind, index)
                    effective_cursor = stored_cursor or (
                        run_started_at - timedelta(seconds=interval_seconds)
                    )
                    cursor_age_seconds = (
                        run_started_at - effective_cursor
                    ).total_seconds()
                    kind_identifier = f"{resource_cfg.kind}-{index}"

                    ocean.metrics.set_metric(
                        name=MetricType.INCREMENTAL_CURSOR_AGE_NAME,
                        labels=[integration_type, kind_identifier],
                        value=cursor_age_seconds,
                    )

                    logger.info(
                        "Starting incremental sync for kind",
                        integration_type=integration_type,
                        integration_id=integration_id,
                        event_id=event.id,
                        kind=resource_cfg.kind,
                        index=index,
                        cursor=effective_cursor.isoformat(),
                        next_cursor=run_started_at.isoformat(),
                    )

                    if not await self._sync_incremental_kind(
                        resource_cfg,
                        index,
                        effective_cursor,
                        run_started_at,
                        cursor_store,
                        integration_type,
                        integration_id,
                        kind_identifier,
                    ):
                        logger.error(
                            "Incremental sync run failed",
                            integration_type=integration_type,
                            integration_id=integration_id,
                            event_id=event.id,
                            interval_seconds=interval_seconds,
                            kinds_total=kinds_total,
                            kinds_succeeded=kinds_succeeded,
                            success=False,
                        )
                        await ocean.app.lifecycle_client.notify_resync_failed(
                            resync_id=event.id,
                            integration_id=ocean.config.integration.identifier,
                            integration_type=ocean.config.integration.type,
                        )
                        return
                    kinds_succeeded += 1

                await ocean.app.lifecycle_client.notify_resync_finished(
                    resync_id=event.id,
                    integration_id=ocean.config.integration.identifier,
                    integration_type=ocean.config.integration.type,
                )

                logger.info(
                    "Incremental sync completed",
                    integration_type=integration_type,
                    integration_id=integration_id,
                    event_id=event.id,
                    interval_seconds=interval_seconds,
                    kinds_total=kinds_total,
                    kinds_succeeded=kinds_succeeded,
                    duration_seconds=round(
                        time.monotonic() - run_started_at_monotonic, 3
                    ),
                    success=True,
                )
            except asyncio.CancelledError:
                ocean.metrics.inc_metric(
                    name=MetricType.INCREMENTAL_RUN_INTERRUPTED_TOTAL_NAME,
                    labels=[integration_type, "cancelled"],
                    value=1,
                )
                logger.warning(
                    "Incremental sync was aborted",
                    integration_type=integration_type,
                    integration_id=integration_id,
                    event_id=event.id,
                    interval_seconds=interval_seconds,
                    kinds_total=kinds_total,
                    kinds_succeeded=kinds_succeeded,
                    during_kind=kind_identifier,
                )
                await ocean.app.lifecycle_client.notify_resync_aborted(
                    resync_id=event.id,
                    integration_id=ocean.config.integration.identifier,
                    integration_type=ocean.config.integration.type,
                )
                raise
            except Exception as e:
                ocean.metrics.inc_metric(
                    name=MetricType.INCREMENTAL_RUN_ERRORS_TOTAL_NAME,
                    labels=[integration_type, "unexpected"],
                    value=1,
                )
                logger.error(
                    "Incremental sync failed unexpectedly",
                    integration_type=integration_type,
                    integration_id=integration_id,
                    event_id=event.id,
                    error=str(e),
                )
                await ocean.app.lifecycle_client.notify_resync_failed(
                    resync_id=event.id,
                    integration_id=ocean.config.integration.identifier,
                    integration_type=ocean.config.integration.type,
                )
                raise
            finally:
                ocean.metrics.clear_sync_context()

    async def _complete_resync(
        self, creation_results: list[KindResult], silent: bool
    ) -> bool:
        """Finish a resync once every kind was processed.

        Mapping, upsert and reconciliation of stale entities happen in the
        data-source-processor once it is notified the resync finished. A resync
        with kind errors is reported as failed, since reconciling a partial state
        would delete entities that were simply not extracted.
        """
        with logger.contextualize(etl_phase=ETLPhase.RECONCILIATION):
            errors = [error for _, kind_errors in creation_results for error in kind_errors]
            success = not errors

            for resync_complete_fn in self.event_strategy.resync_complete:
                await resync_complete_fn()

            async with metric_resource_context(MetricResourceKind.RECONCILIATION):
                ocean.metrics.sync_state = (
                    SyncState.COMPLETED if success else SyncState.FAILED
                )
                ocean.metrics.set_metric(
                    name=MetricType.SUCCESS_NAME,
                    labels=[MetricResourceKind.RECONCILIATION, MetricPhase.RESYNC],
                    value=int(success),
                )
                await ocean.metrics.send_metrics_to_webhook(
                    kind=MetricResourceKind.RECONCILIATION
                )

            notify = (
                ocean.app.lifecycle_client.notify_resync_finished
                if success
                else ocean.app.lifecycle_client.notify_resync_failed
            )
            await notify(
                resync_id=event.id,
                integration_id=ocean.config.integration.identifier,
                integration_type=ocean.config.integration.type,
            )

            if errors:
                message = f"Resync finished with {len(errors)} errors"
                error_group = ExceptionGroup(message, errors)
                if not silent:
                    raise error_group
                logger.error(message, exc_info=error_group)
            else:
                logger.info("Resync finished successfully")
            return success

    @TimeMetric(MetricPhase.RESYNC)
    async def sync_raw_all(
        self,
        _: dict[Any, Any] | None = None,
        trigger_type: TriggerType = "machine",
        user_agent_type: UserAgentType = UserAgentType.exporter,
        silent: bool = True,
    ) -> bool:
        """Perform a full synchronization of raw data.

        Every configured kind is extracted and handed to the data-source-processor, which maps it,
        upserts the entities and reconciles stale entities after the resync finishes.

        Args:
            _ (dict[Any, Any] | None): Unused parameter.
            trigger_type (TriggerType): The type of trigger for the synchronization.
            user_agent_type (UserAgentType): The type of user agent.
            silent (bool): Whether to raise exceptions or handle them silently.
        """
        logger.info("Resync was triggered")

        async with event_context(
            EventType.RESYNC,
            trigger_type=trigger_type,
            attributes={"resync_start_time": datetime.now(timezone.utc)},
        ):
            ocean.metrics.event_id = event.id

            # If a resync is triggered due to a mappings change, we want to make sure that we have the updated version
            # rather than the old cache
            app_config = await self.port_app_config_handler.get_port_app_config(
                use_cache=False
            )
            if not app_config.resources:
                logger.info(
                    "Port app config has no resources configured; "
                    "skipping resync as no-op until mapping is configured"
                )
                await ocean.app.lifecycle_client.notify_resync_started(
                    resync_id=event.id,
                    integration_id=ocean.config.integration.identifier,
                    integration_type=ocean.config.integration.type,
                    started_at=datetime.now(timezone.utc),
                    mapping=app_config.to_dsp_lifecycle_mapping(),
                    sync_type=SyncType.FULL_SYNC.value,
                )
                ocean.metrics.initialize_metrics([MetricResourceKind.RUNTIME])
                async with metric_resource_context(MetricResourceKind.RUNTIME):
                    ocean.metrics.sync_state = SyncState.COMPLETED
                    ocean.metrics.set_metric(
                        name=MetricType.SUCCESS_NAME,
                        labels=[MetricResourceKind.RUNTIME, MetricPhase.RESYNC],
                        value=1,
                    )
                    await ocean.metrics.send_metrics_to_webhook(
                        kind=MetricResourceKind.RUNTIME
                    )
                await ocean.app.lifecycle_client.notify_resync_finished(
                    resync_id=event.id,
                    integration_id=ocean.config.integration.identifier,
                    integration_type=ocean.config.integration.type,
                )
                return True

            logger.info(f"Resync will use the following mappings: {json.loads(app_config.json())}")

            kinds = [
                f"{resource.kind}-{index}"
                for index, resource in enumerate(app_config.resources)
            ]
            ocean.metrics.initialize_metrics(kinds)

            async with metric_resource_context(MetricResourceKind.RUNTIME):
                ocean.metrics.sync_state = SyncState.SYNCING
                ocean.metrics.set_metric(
                    name=MetricType.SUCCESS_NAME,
                    labels=[MetricResourceKind.RUNTIME, MetricPhase.RESYNC],
                    value=0,
                )

                await ocean.metrics.send_metrics_to_webhook(
                    kind=MetricResourceKind.RUNTIME
                )

            # Clear cache
            await ocean.app.cache_provider.clear()
            ocean.port_client.clear_blueprint_cache()

            await ocean.app.lifecycle_client.notify_resync_started(
                resync_id=event.id,
                integration_id=ocean.config.integration.identifier,
                integration_type=ocean.config.integration.type,
                started_at=datetime.now(timezone.utc),
                mapping=app_config.to_dsp_lifecycle_mapping(),
                sync_type=SyncType.FULL_SYNC.value,
            )
            lifecycle_poll_task: asyncio.Task[None] = asyncio.create_task(
                self._poll_for_lifecycle_abort(event.id)
            )

            try:
                try:
                    # Execute resync_start hooks
                    for resync_start_fn in self.event_strategy.resync_start:
                        await resync_start_fn()
                except httpx.HTTPError as e:
                    logger.warning(
                        "A resync_start hook failed with an HTTP error, continuing the resync. "
                        f"Error: {e}\n"
                        f"Response status code: {e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None}\n"
                        f"Response content: {e.response.text if isinstance(e, httpx.HTTPStatusError) else None}\n"
                    )

                creation_results: list[KindResult] = []

                try:
                    for index, resource in enumerate(app_config.resources):
                        logger.bind(resource_kind=resource.kind).info(
                            f"Starting processing resource {resource.kind} with index {index}"
                        )
                        creation_results.append(
                            await self.process_resource(resource, index)
                        )

                except asyncio.CancelledError:
                    if event.external_abort:
                        return False

                    logger.warning(
                        "Resync aborted successfully. The data-source-processor will not reconcile this resync"
                    )
                    await self._handle_resync_abortion(creation_results, app_config)
                    await ocean.app.lifecycle_client.notify_resync_aborted(
                        resync_id=event.id,
                        integration_id=ocean.config.integration.identifier,
                        integration_type=ocean.config.integration.type,
                    )
                    raise
                except Exception as e:
                    logger.error(f"Error in resync: {e}")
                    await self._handle_resync_abortion(creation_results, app_config)
                    await ocean.app.lifecycle_client.notify_resync_failed(
                        resync_id=event.id,
                        integration_id=ocean.config.integration.identifier,
                        integration_type=ocean.config.integration.type,
                    )
                    raise

                return await self._complete_resync(creation_results, silent)
            finally:
                lifecycle_poll_task.cancel()
                try:
                    await lifecycle_poll_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning(
                        "Lifecycle abort poll task failed during cleanup",
                        error=str(e),
                    )
                await ocean.app.cache_provider.clear()
                ocean.port_client.clear_blueprint_cache()
