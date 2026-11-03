import hashlib
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.models import IntegrationFeatureFlag
from port_ocean.core.integrations.mixins.utils import (
    build_lakehouse_data_entry,
    collect_export_env_variables,
    ensure_dsp_processing_available,
    is_live_event_payload_logging_enabled,
    is_redis_live_events_enabled,
    resync_error_handling,
    resync_function_wrapper,
    resync_generator_wrapper,
    selector_hash_from_selector,
    selector_hash_from_resource,
    selector_query_from_resource,
)
from port_ocean.exceptions.core import (
    DSPProcessingUnavailableException,
    OceanAbortException,
)
from port_ocean.core.models import LakehouseOperation


class TestCollectExportEnvVariables:
    def test_returns_none_for_empty_list(self) -> None:
        assert collect_export_env_variables([]) is None

    def test_collects_requested_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOO", "bar")
        monkeypatch.delenv("MISSING", raising=False)

        assert collect_export_env_variables(["FOO", "MISSING"]) == {
            "FOO": "bar",
            "MISSING": None,
        }


class TestBuildLakehouseDataEntry:
    def test_includes_environment_data_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FOO", "bar")

        entry = build_lakehouse_data_entry(
            items=[{"id": "1"}],
            metadata={
                "operation": LakehouseOperation.UPSERT,
                "resource_index": 0,
                "extraction_timestamp": 123,
            },
            export_env_variables=["FOO"],
        )

        assert entry["environment_data"] == {"FOO": "bar"}

    def test_omits_environment_data_when_not_configured(self) -> None:
        entry = build_lakehouse_data_entry(
            items=[{"id": "1"}],
            metadata={
                "operation": LakehouseOperation.UPSERT,
                "resource_index": 0,
                "extraction_timestamp": 123,
            },
            export_env_variables=[],
        )

        assert "environment_data" not in entry


class TestSelectorHashHelpers:
    def test_selector_query_from_resource_returns_trimmed_query(self) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query="  .foo | .bar  "),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        assert selector_query_from_resource(resource) == ".foo | .bar"

    def test_selector_query_from_resource_returns_none_for_whitespace(self) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query="   "),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        assert selector_query_from_resource(resource) is None

    def test_selector_hash_from_query_uses_sha256_hex(self) -> None:
        assert (
            selector_hash_from_selector(".foo")
            == "013b54afaf52ac0983a4ac123b01e809ab7ac8862e67a50f09fcce1293d265c3"
        )

    def test_selector_hash_from_resource_ignores_query_and_hashes_selector(
        self,
    ) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query="  .foo  "),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        expected_selector_payload = (
            resource.selector.dict(
                by_alias=True, exclude_none=True, exclude_unset=True
            )
            if resource.selector
            else {}
        )
        expected_selector_payload.pop("query", None)
        expected_hash = hashlib.sha256(
            json.dumps(
                expected_selector_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        assert selector_hash_from_resource(resource) == expected_hash

    def test_selector_hash_from_resource_is_stable_when_only_query_changes(
        self,
    ) -> None:
        base_resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query=".foo", exportEnvVariables=["MY_VAR"]),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )
        changed_query_resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query=".bar", exportEnvVariables=["MY_VAR"]),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        assert selector_hash_from_resource(
            base_resource
        ) == selector_hash_from_resource(changed_query_resource)

    def test_selector_hash_from_resource_differs_for_implicit_vs_explicit_defaults(
        self,
    ) -> None:
        implicit_defaults = ResourceConfig(
            kind="test-kind",
            selector=Selector(query=".foo"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )
        explicit_defaults = ResourceConfig(
            kind="test-kind",
            selector=Selector(query=".foo", exportEnvVariables=[]),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        assert selector_hash_from_resource(
            implicit_defaults
        ) != selector_hash_from_resource(explicit_defaults)

    def test_selector_hash_from_resource_returns_none_without_selector(self) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )
        resource.selector = None  # type: ignore[assignment]

        assert selector_hash_from_resource(resource) is None

    def test_selector_hash_from_resource_hashes_empty_selector_without_query(
        self,
    ) -> None:
        resource = ResourceConfig(
            kind="test-kind",
            selector=Selector(query=" "),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"test"',
                        properties={},
                        relations={},
                    )
                )
            ),
        )

        expected_selector_payload = (
            resource.selector.dict(
                by_alias=True, exclude_none=True, exclude_unset=True
            )
            if resource.selector
            else {}
        )
        expected_selector_payload.pop("query", None)
        expected_hash = hashlib.sha256(
            json.dumps(
                expected_selector_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        assert selector_hash_from_resource(resource) == expected_hash


class TestResyncWrappersSendExamples:
    @pytest.mark.asyncio
    async def test_resync_function_wrapper_sends_examples(self) -> None:
        raw_results = [{"id": "1"}, {"id": "2"}]

        async def fake_resync(kind: str) -> list[dict[str, Any]]:
            return raw_results

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.port_client.ingest_integration_kind_examples = (
                AsyncMock()
            )

            result = await resync_function_wrapper(
                fake_resync,
                "test-kind",
                send_raw_data_examples_amount=1,
            )

            assert result == raw_results
            mock_ocean_context.port_client.ingest_integration_kind_examples.assert_awaited_once_with(
                "test-kind", [{"id": "1"}], should_log=False
            )

    @pytest.mark.asyncio
    async def test_resync_generator_wrapper_yields_batches_untouched(self) -> None:
        raw_results = [{"id": "1", "items": [{"sub_id": "a"}]}, {"id": "2"}]

        async def fake_generator(kind: str) -> Any:
            yield raw_results

        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.port_client.ingest_integration_kind_examples = (
                AsyncMock()
            )

            batches = [
                batch
                async for batch in resync_generator_wrapper(
                    fake_generator,
                    "test-kind",
                    send_raw_data_examples_amount=1,
                )
            ]

            assert batches == [raw_results]
            assert batches[0] is raw_results
            mock_ocean_context.port_client.ingest_integration_kind_examples.assert_awaited_once_with(
                "test-kind", [{"id": "1", "items": [{"sub_id": "a"}]}], should_log=False
            )


class TestEnsureDspProcessingAvailable:
    @pytest.mark.asyncio
    async def test_passes_when_lakehouse_enabled_and_flags_present(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.lakehouse_enabled = True
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[
                    IntegrationFeatureFlag.LAKEHOUSE_ELIGIBLE,
                    IntegrationFeatureFlag.DATA_SOURCE_PROCESSOR_ENABLED,
                ]
            )

            await ensure_dsp_processing_available()

    @pytest.mark.asyncio
    async def test_raises_when_lakehouse_disabled(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.lakehouse_enabled = False
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock()

            with pytest.raises(
                DSPProcessingUnavailableException, match="LAKEHOUSE_ENABLED"
            ):
                await ensure_dsp_processing_available()

            mock_ocean_context.port_client.get_organization_feature_flags.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_and_names_missing_flags(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.lakehouse_enabled = True
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[IntegrationFeatureFlag.LAKEHOUSE_ELIGIBLE]
            )

            with pytest.raises(DSPProcessingUnavailableException) as exc_info:
                await ensure_dsp_processing_available()

            assert IntegrationFeatureFlag.DATA_SOURCE_PROCESSOR_ENABLED in str(
                exc_info.value
            )
            assert IntegrationFeatureFlag.LAKEHOUSE_ELIGIBLE not in str(exc_info.value)


class TestLiveEventFeatureGates:
    @pytest.mark.asyncio
    async def test_is_live_event_payload_logging_config_off_skips_feature_flags(
        self,
    ) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.live_events.payload_logging_enabled = False
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[IntegrationFeatureFlag.LIVE_EVENTS_PAYLOAD_LOGGING_ENABLED]
            )

            result = await is_live_event_payload_logging_enabled()

        assert result is False
        mock_ocean_context.port_client.get_organization_feature_flags.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_live_event_payload_logging_config_on_feature_flag_off(
        self,
    ) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.live_events.payload_logging_enabled = True
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[]
            )

            result = await is_live_event_payload_logging_enabled()

        assert result is False
        mock_ocean_context.port_client.get_organization_feature_flags.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_live_event_payload_logging_enabled_when_both_gates_on(
        self,
    ) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.live_events.payload_logging_enabled = True
            mock_ocean_context.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[IntegrationFeatureFlag.LIVE_EVENTS_PAYLOAD_LOGGING_ENABLED]
            )

            result = await is_live_event_payload_logging_enabled()

        assert result is True
        mock_ocean_context.port_client.get_organization_feature_flags.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_redis_live_events_enabled_when_org_not_blocked(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.live_events.is_redis_stream_consumer_enabled = (
                True
            )
            mock_ocean_context.port_client.is_organization_blocked = AsyncMock(
                return_value=False
            )

            result = await is_redis_live_events_enabled()

        assert result is True
        mock_ocean_context.port_client.is_organization_blocked.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_redis_live_events_disabled_when_env_opt_in_off(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.live_events.is_redis_stream_consumer_enabled = (
                False
            )
            mock_ocean_context.port_client.is_organization_blocked = AsyncMock(
                return_value=False
            )

            result = await is_redis_live_events_enabled()

        assert result is False
        mock_ocean_context.port_client.is_organization_blocked.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_redis_live_events_disabled_when_org_blocked(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.live_events.is_redis_stream_consumer_enabled = (
                True
            )
            mock_ocean_context.port_client.is_organization_blocked = AsyncMock(
                return_value=True
            )

            result = await is_redis_live_events_enabled()

        assert result is False
        mock_ocean_context.port_client.is_organization_blocked.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_redis_live_events_enabled_uses_local_only_warning_on_exception(
        self,
    ) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean_context:
            mock_ocean_context.config.live_events.is_redis_stream_consumer_enabled = (
                True
            )
            mock_ocean_context.port_client.is_organization_blocked = AsyncMock(
                side_effect=Exception("timeout")
            )

            with patch(
                "port_ocean.core.integrations.mixins.utils.logger"
            ) as mock_logger:
                mock_bound = mock_logger.bind.return_value
                result = await is_redis_live_events_enabled()

        assert result is False
        mock_logger.bind.assert_called_with(local_only=True)
        mock_bound.warning.assert_called_once()
        assert "Failed to check Redis live events settings" in (
            mock_bound.warning.call_args.args[0]
        )


class TestResyncErrorHandling:
    def test_ocean_abort_re_raised_without_logging(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.logger.exception"
        ) as mock_exception:
            with pytest.raises(OceanAbortException, match="tree fetch failed"):
                with resync_error_handling():
                    raise OceanAbortException("tree fetch failed")

            mock_exception.assert_not_called()

    def test_unexpected_exception_is_logged_and_wrapped(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.logger.exception"
        ) as mock_exception:
            with pytest.raises(OceanAbortException, match="Failed to execute resync"):
                with resync_error_handling():
                    raise ValueError("unexpected")

            mock_exception.assert_called_once()

    def test_exception_group_is_logged_and_wrapped(self) -> None:
        abort = OceanAbortException("tree fetch failed")
        group = ExceptionGroup("file failed with 1 error(s)", [abort])
        with patch(
            "port_ocean.core.integrations.mixins.utils.logger.exception"
        ) as mock_exception:
            with pytest.raises(OceanAbortException, match="Failed to execute resync"):
                with resync_error_handling():
                    raise group

            mock_exception.assert_called_once()
