import asyncio
from typing import Any, AsyncGenerator

from httpx import BasicAuth, HTTPStatusError, Timeout
from loguru import logger

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

from utils import (
    SEVERITY_NONE,
    build_component_identifier,
    build_report_identifier,
    build_violation_identifier,
    component_display_name,
    component_version,
    extract_report_id,
    normalize_severity,
    parse_github_owner_repo,
    pick_remediation_versions,
    severity_from_cvss,
    severity_from_threat_level,
    to_absolute_url,
)

# The IQ Server organizations/applications endpoints return the full collection
# in a single response, so we chunk it ourselves to keep batches (and the
# resulting Port bulk-upsert calls) a reasonable size.
BATCH_SIZE = 100
CLIENT_TIMEOUT = 60
MAX_CONCURRENT_REQUESTS = 10


class SonatypeClient:
    """Thin async wrapper over the Sonatype IQ Server (Lifecycle) v2 REST API.

    Authentication is HTTP Basic using a username and a *user token* (works for
    both self-hosted IQ Server and Sonatype Cloud). We deliberately reuse
    Ocean's shared ``http_async_client`` so the integration inherits its
    connection pooling, retry/backoff and timeout behaviour.
    """

    def __init__(self, base_url: str, username: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = http_async_client
        self.client.timeout = Timeout(CLIENT_TIMEOUT)
        # NOTE: do NOT set self.client.auth here. http_async_client is a shared,
        # global client that Ocean also uses to call Port's own API (which sets
        # its own Bearer auth). Setting a persistent .auth would be overwritten
        # by Port's calls, causing our IQ requests to be sent with the wrong
        # credentials (401). Instead we pass Basic auth explicitly per request.
        self._auth = BasicAuth(username, token)
        # Bound the fan-out when we enrich many applications' reports at once.
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def _send_api_request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        """Send a single request. ``path`` is relative to the IQ base URL.

        Returns the parsed JSON body. A 404 is treated as "no data" (empty dict)
        rather than an error, because IQ returns 404 for applications that have
        never been scanned when asking for their reports.
        """
        url = to_absolute_url(self.base_url, path)
        if url is None:
            raise ValueError(f"Could not build absolute URL for path: {path}")
        async with self._semaphore:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                auth=self._auth,
            )
        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            status = e.response.status_code
            if status == 404:
                logger.info(f"No data found at {url} (404), treating as empty")
                return {}
            if status in (401, 403):
                logger.error(
                    f"Authentication/authorization failed ({status}) calling {url}. "
                    "Check iqUsername / iqUserToken and that the account has access "
                    "to the requested organizations and applications."
                )
            else:
                logger.error(
                    f"IQ Server request to {url} failed with {status}: "
                    f"{e.response.text}"
                )
            raise
        return response.json()

    async def verify_connectivity(self) -> None:
        """Fail fast at startup with a clear message if IQ can't be reached/authed.

        Makes a single lightweight call to the organizations endpoint so common
        misconfigurations (wrong URL, bad credentials) surface immediately in the
        logs instead of midway through a resync.
        """
        logger.info(f"Verifying connectivity to IQ Server at {self.base_url}")
        try:
            response = await self._send_api_request("api/v2/organizations")
        except Exception as e:  # noqa: BLE001 - we re-raise after logging context
            logger.error(
                f"Could not connect to Sonatype IQ Server at {self.base_url}: {e}"
            )
            raise
        org_count = len(response.get("organizations", []))
        logger.info(
            f"Connectivity to IQ Server OK — reachable and authenticated "
            f"({org_count} organizations visible to this account)"
        )

    # ----------------------------- Organizations ----------------------------- #

    @cache_iterator_result()
    async def get_organizations(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield all organizations in batches."""
        logger.info("Fetching organizations from Sonatype IQ Server")
        response = await self._send_api_request("api/v2/organizations")
        organizations = response.get("organizations", [])
        logger.info(f"Fetched {len(organizations)} organizations")
        for i in range(0, len(organizations), BATCH_SIZE):
            yield organizations[i : i + BATCH_SIZE]

    async def get_single_organization(self, organization_id: str) -> dict[str, Any]:
        """Fetch a single organization by its internal ID."""
        return await self._send_api_request(f"api/v2/organizations/{organization_id}")

    # ----------------------------- Applications ------------------------------ #

    @cache_iterator_result()
    async def get_applications(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield all applications in batches."""
        logger.info("Fetching applications from Sonatype IQ Server")
        response = await self._send_api_request("api/v2/applications")
        applications = response.get("applications", [])
        logger.info(f"Fetched {len(applications)} applications")
        for i in range(0, len(applications), BATCH_SIZE):
            yield applications[i : i + BATCH_SIZE]

    async def get_application_by_public_id(
        self, public_id: str
    ) -> dict[str, Any] | None:
        """Fetch a single application by its human-facing public ID."""
        response = await self._send_api_request(
            "api/v2/applications", params={"publicId": public_id}
        )
        applications = response.get("applications", [])
        return applications[0] if applications else None

    # ------------------------- Source Control (SCM) -------------------------- #

    async def get_application_source_control(
        self, application: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Fetch the Source Control Management config for one application.

        Returns ``None`` when the application has no SCM configured — IQ
        returns 404 in that case, which ``_send_api_request`` already turns
        into ``{}`` (the same convention used for unscanned applications'
        reports), so we treat an empty response the same way here.

        Only the root organization's *access token* can be inherited; the
        ``repositoryUrl`` itself is always application-specific (each
        application maps to exactly one repo), so a single per-application GET
        is sufficient — there's no org-level fallback to also check.
        """
        response = await self._send_api_request(
            f"api/v2/sourceControl/application/{application['id']}"
        )
        if not response or not response.get("repositoryUrl"):
            return None

        # The GET response should not echo back the write-only `token` field,
        # but strip it defensively so a credential can never end up in the
        # catalog if a future IQ version changes that behavior.
        response = {k: v for k, v in response.items() if k != "token"}

        owner, repo = parse_github_owner_repo(
            response.get("repositoryUrl"), response.get("provider")
        )

        return {
            **response,
            # Same identifier as the application so the sourceControl kind can
            # upsert sonatypeApplication and set githubRepository without
            # creating a parallel entity. Prefer the application name for
            # __title so this upsert does not rename the app to its repo URL.
            "__identifier": application["id"],
            "__title": application.get("name")
            or response.get("repositoryUrl")
            or application["id"],
            "__applicationId": application["id"],
            "__githubRepository": f"{owner}/{repo}" if owner and repo else None,
        }

    # ------------------------------- Reports --------------------------------- #

    async def get_application_report_summaries(
        self, application_internal_id: str
    ) -> list[dict[str, Any]]:
        """Return the latest report summary per stage for an application.

        The endpoint returns a JSON array; each element describes the most
        recent report for a given stage (build, stage-release, release, ...).
        """
        response = await self._send_api_request(
            f"api/v2/reports/applications/{application_internal_id}"
        )
        # An application with no scans yields {} (from our 404 handling).
        return response if isinstance(response, list) else []

    async def get_policy_report(self, report_data_url: str) -> dict[str, Any]:
        """Fetch the component-oriented policy report.

        ``report_data_url`` is the server-provided path
        (``api/v2/applications/<id>/reports/<reportId>``); appending ``/policy``
        avoids any ambiguity between internal and public application IDs.
        """
        return await self._send_api_request(f"{report_data_url.strip('/')}/policy")

    async def get_raw_report(self, report_data_url: str) -> dict[str, Any]:
        """Fetch the raw report: components with license and security (CVE) data."""
        return await self._send_api_request(f"{report_data_url.strip('/')}/raw")

    # Stages IQ computes remediation for, in the order we fall back through them.
    # The report's own stage is tried first; if it yields nothing (e.g. the
    # source/SCM stage, which does not carry remediation data) we retry against
    # the stages that do.
    REMEDIATION_FALLBACK_STAGES = ("build", "stage-release", "release", "operate")

    async def get_component_remediation(
        self,
        application_internal_id: str,
        stage_id: str,
        component_identifier: dict[str, Any],
        package_url: str | None = None,
    ) -> dict[str, str | None]:
        """Ask IQ for the recommended fix versions for a single component.

        Returns the reduced set of recommended versions (or all-None if IQ has
        no suggestion). Failures are swallowed to None so one component can't
        break a whole resync.

        We send ``packageUrl`` when available because IQ gives it precedence over
        ``componentIdentifier`` and it is the most reliable way to pin a
        component (notably for npm, whose coordinates differ from the raw-report
        shape). ``includeParentRemediation`` lets transitive components resolve a
        fix via their nearest parent dependency.

        IQ only computes remediation for the build/stage-release/release/operate
        stages, not for the source (SCM) stage. Since an application's most recent
        report is frequently on the source stage, we try the report's own stage
        first and then fall back through the remediation-bearing stages, returning
        the first non-empty result.
        """
        body: dict[str, Any] = (
            {"packageUrl": package_url}
            if package_url
            else {"componentIdentifier": component_identifier}
        )
        component_ref = package_url or component_identifier

        # Report's own stage first, then the remediation-bearing stages (deduped,
        # order preserved).
        stages_to_try: list[str] = []
        for candidate in (stage_id, *self.REMEDIATION_FALLBACK_STAGES):
            if candidate and candidate not in stages_to_try:
                stages_to_try.append(candidate)

        for stage in stages_to_try:
            try:
                response = await self._send_api_request(
                    f"api/v2/components/remediation/application/{application_internal_id}",
                    params={"stageId": stage, "includeParentRemediation": "true"},
                    method="POST",
                    json_data=body,
                )
            except Exception as e:  # noqa: BLE001 - remediation is best-effort
                logger.warning(
                    f"Remediation lookup failed for {component_ref} at stage "
                    f"{stage}: {e}"
                )
                continue
            version_changes = (response.get("remediation") or {}).get(
                "versionChanges"
            ) or []
            if version_changes:
                return pick_remediation_versions(version_changes)

        logger.debug(
            f"No remediation found for {component_ref} across stages "
            f"{stages_to_try}"
        )
        return pick_remediation_versions([])

    # ----------------------- Enrichment / aggregation ------------------------ #

    def _build_report_entity(
        self,
        application: dict[str, Any],
        report_summary: dict[str, Any],
        policy_report: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine a report summary with computed severity counts."""
        stage = report_summary.get("stage", "unknown")
        report_id = extract_report_id(report_summary)
        components = policy_report.get("components") or []

        counts = {"critical": 0, "severe": 0, "moderate": 0, "low": 0, "none": 0}
        components_with_violations = 0
        for component in components:
            violations = component.get("violations") or []
            if violations:
                components_with_violations += 1
            for violation in violations:
                severity = severity_from_threat_level(
                    violation.get("policyThreatLevel")
                )
                counts[severity] += 1

        return {
            **report_summary,
            "__identifier": build_report_identifier(application["id"], stage),
            "__title": f"{application.get('name', application['id'])} - {stage}",
            "__applicationId": application["id"],
            "__reportId": report_id,
            "__stage": stage,
            "__url": to_absolute_url(
                self.base_url, report_summary.get("reportHtmlUrl")
            ),
            "__pdfUrl": to_absolute_url(
                self.base_url, report_summary.get("reportPdfUrl")
            ),
            "__criticalCount": counts["critical"],
            "__severeCount": counts["severe"],
            "__moderateCount": counts["moderate"],
            "__lowCount": counts["low"],
            "__componentsWithViolations": components_with_violations,
            "__totalComponents": (policy_report.get("counts") or {}).get(
                "totalComponentCount"
            ),
        }

    def _build_violation_entities(
        self,
        application: dict[str, Any],
        report_summary: dict[str, Any],
        policy_report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Flatten a policy report into individual policy-violation entities."""
        stage = report_summary.get("stage", "unknown")
        # Key violations on the stable application-stage report identifier
        # (same as reports/components), not the volatile per-scan reportId.
        report_identifier = build_report_identifier(application["id"], stage)
        report_url = to_absolute_url(self.base_url, report_summary.get("reportHtmlUrl"))

        violations: list[dict[str, Any]] = []
        for component in policy_report.get("components") or []:
            component_hash = component.get("hash", "unknown")
            display_name = component_display_name(component)
            for violation in component.get("violations") or []:
                policy_id = violation.get("policyId", "unknown")
                violations.append(
                    {
                        **violation,
                        "__identifier": build_violation_identifier(
                            report_identifier, component_hash, policy_id
                        ),
                        "__title": f"{violation.get('policyName', 'Policy')} - {display_name}",
                        "__applicationId": application["id"],
                        "__reportIdentifier": report_identifier,
                        "__stage": stage,
                        "__severity": severity_from_threat_level(
                            violation.get("policyThreatLevel")
                        ),
                        "__componentDisplayName": display_name,
                        "__packageUrl": component.get("packageUrl"),
                        "__componentHash": component_hash,
                        "__url": report_url,
                    }
                )
        return violations

    async def _build_component_and_vulnerability_entities(
        self,
        application: dict[str, Any],
        report_summary: dict[str, Any],
        raw_report: dict[str, Any],
        include_remediation: bool,
    ) -> dict[str, list[dict[str, Any]]]:
        """Flatten a raw report into component + vulnerability (CVE) entities.

        Each component becomes one ``component`` entity that relates to the CVE
        entities affecting it. CVEs are emitted as *global* ``vulnerability``
        entities keyed by their reference (e.g. CVE-2021-44228), so the same CVE
        is deduplicated across every application that is exposed to it.
        """
        stage = report_summary.get("stage", "unknown")
        report_identifier = build_report_identifier(application["id"], stage)
        report_url = to_absolute_url(self.base_url, report_summary.get("reportHtmlUrl"))

        components: list[dict[str, Any]] = []
        vulnerabilities: dict[str, dict[str, Any]] = {}
        remediation_attempts = 0
        remediation_resolved = 0

        for component in raw_report.get("components") or []:
            component_hash = component.get("hash", "unknown")
            display_name = component_display_name(component)
            security_issues = (component.get("securityData") or {}).get(
                "securityIssues"
            ) or []

            cve_references: list[str] = []
            max_cvss = 0.0
            for issue in security_issues:
                reference = issue.get("reference")
                if not reference:
                    continue
                cve_references.append(reference)
                score = issue.get("severity") or 0.0
                max_cvss = max(max_cvss, float(score))
                # normalize_severity always returns a string (including "none"),
                # so ``or severity_from_cvss`` would never run. Fall back to
                # CVSS when the threat category is missing/unrecognized.
                severity = normalize_severity(issue.get("threatCategory"))
                if severity == SEVERITY_NONE:
                    severity = severity_from_cvss(score)
                # Global CVE entity (last write wins across occurrences).
                vulnerabilities[reference] = {
                    "__identifier": reference,
                    "__title": reference,
                    "reference": reference,
                    "source": issue.get("source"),
                    "url": issue.get("url"),
                    "cvssScore": score,
                    "severity": severity,
                    "threatCategory": issue.get("threatCategory"),
                    "status": issue.get("status"),
                }

            remediation: dict[str, str | None] = {
                "recommendedVersion": None,
                "recommendedRemediationType": None,
                "recommendedNonFailingVersion": None,
            }
            if include_remediation and (security_issues or component.get("violations")):
                remediation_attempts += 1
                remediation = await self.get_component_remediation(
                    application["id"],
                    stage,
                    component.get("componentIdentifier") or {},
                    package_url=component.get("packageUrl"),
                )
                if remediation.get("recommendedVersion") or remediation.get(
                    "recommendedNonFailingVersion"
                ):
                    remediation_resolved += 1

            license_data = component.get("licenseData") or {}
            licenses = (
                license_data.get("effectiveLicenses")
                or license_data.get("declaredLicenses")
                or []
            )
            components.append(
                {
                    **component,
                    "__identifier": build_component_identifier(
                        application["id"], stage, component_hash
                    ),
                    "__title": display_name,
                    "__applicationId": application["id"],
                    "__reportIdentifier": report_identifier,
                    "__stage": stage,
                    "__displayName": display_name,
                    "__packageUrl": component.get("packageUrl"),
                    "__format": (component.get("componentIdentifier") or {}).get(
                        "format"
                    ),
                    "__version": component_version(component),
                    "__matchState": component.get("matchState"),
                    "__directDependency": (component.get("dependencyData") or {}).get(
                        "directDependency"
                    ),
                    "__licenses": [
                        lic.get("licenseId") for lic in licenses if lic.get("licenseId")
                    ],
                    "__maxCvssScore": max_cvss,
                    "__securityIssueCount": len(security_issues),
                    "__cveReferences": cve_references,
                    "__url": report_url,
                    **remediation,
                }
            )

        if include_remediation:
            logger.info(
                f"[remediation] app={application.get('publicId', application['id'])} "
                f"stage={stage}: attempted={remediation_attempts} "
                f"resolved={remediation_resolved}"
            )

        return {
            "components": components,
            "vulnerabilities": list(vulnerabilities.values()),
        }

    def _report_base_url(
        self, application: dict[str, Any], report_summary: dict[str, Any]
    ) -> str:
        """Build the report-detail base path: api/v2/applications/{publicId}/reports/{reportId}.

        IMPORTANT: the /policy, /raw and reportDataUrl routes are keyed by the
        application's PUBLIC id, not its internal id (the internal id is only for
        the applications/reports-list endpoints). We construct the path from the
        public id and the parsed report id so it is correct regardless of IQ
        version (some versions return reportDataUrl already suffixed with /raw).
        """
        public_id = application.get("publicId") or application["id"]
        report_id = extract_report_id(report_summary)
        return f"api/v2/applications/{public_id}/reports/{report_id}"

    async def _scan_data_for_report_summary(
        self, application: dict[str, Any], report_summary: dict[str, Any]
    ) -> dict[str, Any]:
        """Fetch the policy report for one summary and build report + violations."""
        report_data_url = self._report_base_url(application, report_summary)
        policy_report = await self.get_policy_report(report_data_url)
        return {
            "report": self._build_report_entity(
                application, report_summary, policy_report
            ),
            "violations": self._build_violation_entities(
                application, report_summary, policy_report
            ),
        }

    async def get_application_scan_data(
        self, application: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        """Return all report entities and violation entities for an application."""
        summaries = await self.get_application_report_summaries(application["id"])
        if not summaries:
            return {"reports": [], "violations": []}

        results = await asyncio.gather(
            *[
                self._scan_data_for_report_summary(application, summary)
                for summary in summaries
            ]
        )
        reports = [r["report"] for r in results]
        violations = [v for r in results for v in r["violations"]]
        return {"reports": reports, "violations": violations}

    async def get_scan_data_for_single_report(
        self, application: dict[str, Any], stage: str, report_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Build report + violations for one specific report (used by webhooks).

        We reconstruct the report summary from the identifiers carried in the
        Application Evaluation webhook payload, so we only fetch the single
        policy report that actually changed.
        """
        summary = {
            "stage": stage,
            "reportHtmlUrl": (
                f"ui/links/application/{application.get('publicId', application['id'])}"
                f"/report/{report_id}"
            ),
        }
        data = await self._scan_data_for_report_summary(application, summary)
        return {"reports": [data["report"]], "violations": data["violations"]}

    # ----------------- Components / vulnerabilities aggregation -------------- #

    def _report_summary_for(
        self, application: dict[str, Any], stage: str, report_id: str
    ) -> dict[str, Any]:
        return {
            "stage": stage,
            "reportHtmlUrl": (
                f"ui/links/application/{application.get('publicId', application['id'])}"
                f"/report/{report_id}"
            ),
        }

    async def get_application_component_data(
        self, application: dict[str, Any], include_remediation: bool = False
    ) -> dict[str, list[dict[str, Any]]]:
        """Return component and vulnerability (CVE) entities for an application.

        Fetches the raw report per stage (license + security data) and, when
        ``include_remediation`` is set, enriches vulnerable components with the
        recommended upgrade versions from IQ's Component Remediation API.
        """
        summaries = await self.get_application_report_summaries(application["id"])
        if not summaries:
            return {"components": [], "vulnerabilities": []}

        all_components: list[dict[str, Any]] = []
        vulnerabilities: dict[str, dict[str, Any]] = {}
        for summary in summaries:
            raw_report = await self.get_raw_report(
                self._report_base_url(application, summary)
            )
            built = await self._build_component_and_vulnerability_entities(
                application, summary, raw_report, include_remediation
            )
            all_components.extend(built["components"])
            for vuln in built["vulnerabilities"]:
                vulnerabilities[vuln["__identifier"]] = vuln

        return {
            "components": all_components,
            "vulnerabilities": list(vulnerabilities.values()),
        }

    async def get_component_data_for_single_report(
        self,
        application: dict[str, Any],
        stage: str,
        report_id: str,
        include_remediation: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        """Build component + vulnerability entities for one report (webhooks)."""
        summary = self._report_summary_for(application, stage, report_id)
        raw_report = await self.get_raw_report(
            self._report_base_url(application, summary)
        )
        return await self._build_component_and_vulnerability_entities(
            application, summary, raw_report, include_remediation
        )
