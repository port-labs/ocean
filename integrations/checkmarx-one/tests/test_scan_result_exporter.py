import pytest
from unittest.mock import AsyncMock
from typing import Any, List

from checkmarx_one.core.exporters.scan_result_exporter import (
    CheckmarxScanResultExporter,
)
from base_client import BaseCheckmarxClient


class TestCheckmarxScanResultExporter:
    """Test cases for CheckmarxScanResultExporter."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock BaseCheckmarxClient for testing."""
        mock_client = AsyncMock(spec=BaseCheckmarxClient)
        mock_client._send_api_request = AsyncMock()

        # Create an async generator for _get_paginated_resources
        async def mock_paginated_resources(*args, **kwargs):
            # This will be set up in individual tests
            pass

        mock_client._get_paginated_resources = mock_paginated_resources
        return mock_client

    @pytest.fixture
    def scan_result_exporter(
        self, mock_client: AsyncMock
    ) -> CheckmarxScanResultExporter:
        """Create a CheckmarxScanResultExporter instance for testing."""
        return CheckmarxScanResultExporter(mock_client)

    @pytest.fixture
    def sample_scan_result(self) -> dict[str, Any]:
        """Sample scan result data for testing."""
        return {
            "type": "sast",
            "id": "1bb31sbYSVLxEDzwTfnlVAtj/qg=",
            "similarityId": "-70323986",
            "status": "NEW",
            "state": "TO_VERIFY",
            "severity": "HIGH",
            "confidenceLevel": 0,
            "created": "2024-11-10T14:00:55Z",
            "firstFoundAt": "2024-11-10T13:36:04Z",
            "foundAt": "2024-11-10T14:00:55Z",
            "firstScanId": "a08b682b-a425-49cc-8503-d881102cfc50",
            "description": "The JWT is not properly verified at the decode in 12 at the file /packages/plugins/users-permissions/server/services/providers-registry.js.",
            "data": {
                "queryId": "5199072880887211000a",
                "queryName": "JWT_No_Signature_Verification",
                "group": "JavaScript_Server_Side_Vulnerabilities",
                "resultHash": "1bb31sbYSVLxEDzwTfnlVAtj/qg=",
                "languageName": "JavaScript",
                "nodes": [
                    {
                        "id": "eppp0lOl2xHFRv9NHXEsId7H9N0=",
                        "line": 12,
                        "name": "decode",
                        "column": 11,
                        "length": 6,
                        "method": "Cx78ef2149",
                        "nodeID": 199240,
                        "domType": "MethodInvokeExpr",
                        "fileName": "/packages/plugins/users-permissions/server/services/providers-registry.js",
                        "fullName": "CxJSNS_55a30431.jwt.decode",
                        "typeName": "decode",
                        "methodLine": 8,
                        "definitions": "0",
                    }
                ],
            },
            "comments": {},
            "vulnerabilityDetails": {
                "cweId": "CWE-287",
                "compliances": [
                    "OWASP Top 10 2021",
                    "OWASP Top 10 API",
                    "SANS top 25",
                    "ASA Premium",
                    "CWE top 25",
                    "MOIS(KISA) Secure Coding 2021",
                    "OWASP ASVS",
                ],
            },
        }

    @pytest.fixture
    def sample_scan_results_batch(
        self, sample_scan_result: dict[str, Any]
    ) -> List[dict[str, Any]]:
        """Sample batch of scan results for testing."""
        return [
            sample_scan_result,
            {
                "type": "sca",
                "id": "CVE-2023-37466",
                "similarityId": "CVE-2023-37466",
                "status": "NEW",
                "state": "TO_VERIFY",
                "severity": "CRITICAL",
                "confidenceLevel": 0,
                "created": "2024-04-30T09:04:02Z",
                "firstFoundAt": "2024-04-30T09:04:02Z",
                "foundAt": "2024-04-30T09:04:02Z",
                "firstScanId": "29d26e5b-2609-46cf-9323-db1b7a61dba8",
                "description": 'The package vm2 is an advanced vm/sandbox for "Node.js". The library contains critical security issues and should not be used for production.',
                "data": {
                    "packageIdentifier": "Npm-vm2-3.9.17",
                    "publishedAt": "2023-07-14T00:15:00+00:00",
                    "recommendations": "",
                    "recommendedVersion": "",
                    "exploitableMethods": "",
                    "packageData": [
                        {
                            "url": "https://github.com/advisories/GHSA-cchq-frgv-rjh5",
                            "type": "Advisory",
                        }
                    ],
                },
                "comments": {"comments": ""},
                "vulnerabilityDetails": {
                    "cvssScore": 10,
                    "cveName": "CVE-2023-37466",
                    "cweId": "CWE-94",
                    "cvss": {
                        "version": 3,
                        "attackVector": "NETWORK",
                        "availability": "HIGH",
                        "cvss3severity": "Critical",
                        "confidentiality": "HIGH",
                        "attackComplexity": "LOW",
                        "exploitCodeMaturity": "3.9",
                    },
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_get_scan_results_without_parameters(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results without any parameters."""
        options = {"scan_id": "scan-123"}

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1
        assert results[0] == sample_scan_results_batch

    @pytest.mark.asyncio
    async def test_get_scan_results_with_limit(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with limit parameter."""
        options = {"scan_id": "scan-123", "limit": 50}

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scan_results_with_offset(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with offset parameter."""
        options = {"scan_id": "scan-123", "offset": 100}

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scan_results_with_severity_filter(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with severity filter."""
        options = {"scan_id": "scan-123", "severity": ["HIGH", "CRITICAL"]}

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scan_results_with_state_filter(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with state filter."""
        options = {"scan_id": "scan-123", "state": ["TO_VERIFY", "CONFIRMED"]}

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scan_results_with_status_filter(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with status filter."""
        options = {"scan_id": "scan-123", "status": ["NEW", "RECURRENT"]}

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scan_results_with_sort(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with sort parameter."""
        options = {"scan_id": "scan-123", "sort": ["+severity", "-status"]}

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scan_results_with_exclude_result_types(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with exclude_result_types parameter."""
        options = {"scan_id": "scan-123", "exclude_result_types": "DEV_AND_TEST"}

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scan_results_with_all_parameters(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with all parameters."""
        options = {
            "scan_id": "scan-123",
            "limit": 25,
            "offset": 50,
            "severity": ["HIGH", "CRITICAL"],
            "state": ["TO_VERIFY"],
            "status": ["NEW"],
            "sort": ["+severity"],
            "exclude_result_types": "DEV_AND_TEST",
        }

        async def mock_paginated_resources(*args, **kwargs):
            yield sample_scan_results_batch

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_scan_results_multiple_batches(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_results_batch: List[dict[str, Any]],
    ) -> None:
        """Test getting scan results with multiple batches."""
        batch1 = sample_scan_results_batch[:1]
        batch2 = sample_scan_results_batch[1:]

        async def mock_paginated_resources(*args, **kwargs):
            yield batch1
            yield batch2

        mock_client._get_paginated_resources = mock_paginated_resources

        options = {"scan_id": "scan-123"}
        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 2
        assert results[0] == batch1
        assert results[1] == batch2

    @pytest.mark.asyncio
    async def test_get_scan_results_empty_result(
        self, scan_result_exporter: CheckmarxScanResultExporter, mock_client: AsyncMock
    ) -> None:
        """Test getting scan results with empty result."""
        options = {"scan_id": "scan-123"}

        async def mock_paginated_resources(*args, **kwargs):
            # Yield nothing - empty result
            if False:  # This ensures it's an async generator
                yield []

        mock_client._get_paginated_resources = mock_paginated_resources

        results = []
        async for batch in scan_result_exporter.get_scan_results(options):
            results.append(batch)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_scan_results_missing_scan_id(
        self, scan_result_exporter: CheckmarxScanResultExporter
    ) -> None:
        """Test getting scan results without scan_id raises ValueError."""
        options = {}

        with pytest.raises(
            ValueError, match="scan_id is required for getting scan results"
        ):
            async for batch in scan_result_exporter.get_scan_results(options):
                pass

    @pytest.mark.asyncio
    async def test_get_scan_results_none_options(
        self, scan_result_exporter: CheckmarxScanResultExporter
    ) -> None:
        """Test getting scan results with None options raises ValueError."""
        with pytest.raises(
            ValueError, match="scan_id is required for getting scan results"
        ):
            async for batch in scan_result_exporter.get_scan_results(None):
                pass

    @pytest.mark.asyncio
    async def test_get_scan_results_exception_handling(
        self, scan_result_exporter: CheckmarxScanResultExporter, mock_client: AsyncMock
    ) -> None:
        """Test exception handling in get_scan_results."""
        options = {"scan_id": "scan-123"}

        async def mock_paginated_resources(*args, **kwargs):
            if True:  # This ensures it's an async generator
                raise Exception("Pagination Error")
            yield []

        mock_client._get_paginated_resources = mock_paginated_resources

        with pytest.raises(Exception, match="Pagination Error"):
            async for batch in scan_result_exporter.get_scan_results(options):
                pass

    @pytest.mark.asyncio
    async def test_get_scan_result_by_id(
        self,
        scan_result_exporter: CheckmarxScanResultExporter,
        mock_client: AsyncMock,
        sample_scan_result: dict[str, Any],
    ) -> None:
        """Test getting a specific scan result by ID."""
        mock_client._send_api_request.return_value = sample_scan_result

        result = await scan_result_exporter.get_scan_result_by_id(
            "scan-123", "result-456"
        )

        mock_client._send_api_request.assert_called_once_with(
            "/results", params={"scan-id": "scan-123", "limit": 1}
        )
        assert result == sample_scan_result

    def test_scan_result_exporter_inheritance(
        self, scan_result_exporter: CheckmarxScanResultExporter
    ) -> None:
        """Test that CheckmarxScanResultExporter properly inherits from AbstractCheckmarxExporter."""
        from checkmarx_one.core.exporters.abstract_exporter import (
            AbstractCheckmarxExporter,
        )

        assert isinstance(scan_result_exporter, AbstractCheckmarxExporter)

    def test_scan_result_exporter_docstring(self) -> None:
        """Test that CheckmarxScanResultExporter has proper documentation."""
        assert CheckmarxScanResultExporter.__doc__ is not None
        assert (
            "Exporter for Checkmarx One scan results"
            in CheckmarxScanResultExporter.__doc__
        )

    def test_get_scan_results_docstring(self) -> None:
        """Test that get_scan_results method has proper documentation."""
        assert CheckmarxScanResultExporter.get_scan_results.__doc__ is not None
        assert (
            "Get scan results from Checkmarx One"
            in CheckmarxScanResultExporter.get_scan_results.__doc__
        )

    def test_get_scan_result_by_id_docstring(self) -> None:
        """Test that get_scan_result_by_id method has proper documentation."""
        assert CheckmarxScanResultExporter.get_scan_result_by_id.__doc__ is not None
        assert (
            "Get a specific scan result by ID"
            in CheckmarxScanResultExporter.get_scan_result_by_id.__doc__
        )
