import asyncio
import json
import typing
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, AsyncIterator, List, Optional, Tuple, Union, Set

import aiolimiter
import anyio.to_thread
import yaml
import gitlab.exceptions
from gitlab import Gitlab, GitlabError, GitlabList
from gitlab.base import RESTObject
from gitlab.v4.objects import (
    Group,
    GroupMergeRequest,
    Issue,
    MergeRequest,
    Project,
    ProjectFile,
    ProjectPipeline,
    ProjectPipelineJob,
    ProjectLabel,
    Hook,
)
from gitlab_integration.core.async_fetcher import AsyncFetcher
from gitlab_integration.core.entities import generate_entity_from_port_yaml
from gitlab_integration.core.utils import (
    does_pattern_apply,
    convert_glob_to_gitlab_patterns,
)
from loguru import logger
from yaml.parser import ParserError

from port_ocean.context.event import event
from port_ocean.core.models import Entity
import functools

PROJECTS_CACHE_KEY = "__cache_all_projects"


MAX_ALLOWED_FILE_SIZE_IN_BYTES = 1024 * 1024  # 1MB
GITLAB_SEARCH_RATE_LIMIT = 100

if TYPE_CHECKING:
    from gitlab_integration.git_integration import GitlabPortAppConfig

MAXIMUM_CONCURRENT_TASK = 10
semaphore = asyncio.BoundedSemaphore(MAXIMUM_CONCURRENT_TASK)
JSON_SUFFIX = (".json",)
YAML_SUFFIX = (".yaml", ".yml")


class GitlabService:
    all_events_in_webhook: list[str] = [
        "push_events",
        "merge_requests_events",
        "issues_events",
        "job_events",
        "pipeline_events",
        "releases_events",
        "tag_push_events",
        "subgroup_events",
        "confidential_issues_events",
        "member_events",
    ]

    def __init__(
        self,
        gitlab_client: Gitlab,
        app_host: str,
        group_mapping: List[str],
    ):
        self.gitlab_client = gitlab_client
        self.app_host = app_host
        self.group_mapping = group_mapping
        self._search_rate_limiter = aiolimiter.AsyncLimiter(
            GITLAB_SEARCH_RATE_LIMIT * 0.95, 60
        )

    async def get_group_hooks(self, group: RESTObject) -> AsyncIterator[List[Hook]]:
        async for hooks_batch in AsyncFetcher.fetch_batch(group.hooks.list):
            hooks = typing.cast(List[Hook], hooks_batch)
            yield hooks

    async def _get_webhook_for_group(self, group: RESTObject) -> RESTObject | None:
        webhook_url = f"{self.app_host}/integration/hook/{group.get_id()}"
        logger.info(
            f"Getting webhook for group {group.get_id()} with url {webhook_url}"
        )
        async for hook_batch in self.get_group_hooks(group):
            for hook in hook_batch:
                if hook.url == webhook_url:
                    logger.info(
                        f"Found webhook for group {group.get_id()} with id {hook.id} and url {hook.url}"
                    )
                    return hook
        return None

    async def _delete_group_webhook(self, group: RESTObject, hook_id: int) -> None:
        logger.info(f"Deleting webhook with id {hook_id} in group {group.get_id()}")
        try:
            await AsyncFetcher.fetch_single(group.hooks.delete, hook_id)
            logger.info(f"Deleted webhook for {group.get_id()}")
        except Exception as e:
            logger.error(f"Failed to delete webhook for {group.get_id()} error={e}")

    async def _create_group_webhook(
        self, group: RESTObject, events: list[str] | None
    ) -> None:
        webhook_events = {
            event: event in (events if events else self.all_events_in_webhook)
            for event in self.all_events_in_webhook
        }

        logger.info(
            f"Creating webhook for group {group.get_id()} with events: {[event for event in webhook_events if webhook_events[event]]}"
        )
        try:
            resp = await AsyncFetcher.fetch_single(
                group.hooks.create,
                {
                    "url": f"{self.app_host}/integration/hook/{group.get_id()}",
                    **webhook_events,
                },
            )
            logger.info(
                f"Created webhook for group {group.get_id()}, webhook id={resp.id}, url={resp.url}"
            )
        except Exception as e:
            logger.exception(
                f"Failed to create webhook for group {group.get_id()} error={e}"
            )

    def _get_changed_files_between_commits(
        self, project_id: int, head: str
    ) -> Union[GitlabList, list[dict[str, Any]]]:
        project = self.gitlab_client.projects.get(project_id)
        return project.commits.get(head).diff()

    async def get_all_file_paths(
        self,
        project: Project,
        path: str | List[str],
        commit_sha: str,
        return_files_only: bool = False,
    ) -> list[str]:
        """
        This function iterates through repository tree pages and returns all files in the repository that match the path pattern.

        The search features of gitlab only support searches on the default branch as for writing this code,
        So in order to check the existence of a file in a specific branch, we need to fetch the entire repository tree.
        https://docs.gitlab.com/ee/user/search/advanced_search.html#known-issues
        """
        if not isinstance(path, list):
            path = [path]
        try:
            files = await AsyncFetcher.fetch_repository_tree(
                project, ref=commit_sha, recursive=True, get_all=True
            )
        except GitlabError as err:
            if err.response_code != 404:
                raise err

            logger.warning(
                f"Failed to retrieve project tree for commit sha: {commit_sha} as it was not found."
            )
            files = []
        return [
            file["path"]
            for file in files
            if (not return_files_only or file["type"] == "blob")
            and does_pattern_apply(path, file["path"] or "")
        ]

    async def search_files_in_project(
        self, project: Project, path: str | List[str]
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Search for files in a GitLab project matching the given path pattern(s)."""
        logger.info(
            f"Searching project {project.path_with_namespace} for files with path pattern {path}"
        )
        gitlab_patterns = convert_glob_to_gitlab_patterns(path)

        files_found = False
        async for matched_files in self._process_search_patterns(
            project, gitlab_patterns
        ):
            yield matched_files
            files_found = True

        if not files_found:
            logger.info(
                f"No files with content found for project {project.path_with_namespace} for path {path}"
            )

    async def _process_search_patterns(
        self, project: Project, gitlab_patterns: List[str]
    ) -> AsyncIterator[list[dict]]:
        for pattern in gitlab_patterns:
            async with self._search_rate_limiter:
                async for search_results in AsyncFetcher.fetch_batch(
                    project.search,
                    scope="blobs",
                    search=f"path:{pattern}",
                    search_type="advanced",
                    retry_transient_errors=True,
                ):
                    if not search_results:
                        continue

                    files_list = typing.cast(List[dict[str, Any]], search_results)
                    matching_files = [
                        f for f in files_list if does_pattern_apply(pattern, f["path"])
                    ]
                    logger.info(
                        f"Found {len(matching_files)} files in project {project.path_with_namespace} "
                        f"for pattern {pattern}"
                    )
                    if not matching_files:
                        continue

                    content_tasks = [
                        self.get_and_parse_single_file(
                            project, file["path"], project.default_branch
                        )
                        for file in matching_files
                    ]

                    parsed_files = await asyncio.gather(*content_tasks)
                    files_with_content = [file for file in parsed_files if file]

                    if files_with_content:
                        logger.info(
                            f"Found {len(files_with_content)} files with content in "
                            f"{project.path_with_namespace} matching {pattern}"
                        )
                        yield files_with_content

    async def _get_entities_from_git(
        self, project: Project, file_path: str | List[str], sha: str, ref: str
    ) -> List[Entity]:
        try:
            file_content = await AsyncFetcher.fetch_single(
                project.files.get, file_path, sha
            )

            entities = await anyio.to_thread.run_sync(
                yaml.safe_load, file_content.decode()
            )
            raw_entities = [
                Entity(**entity_data)
                for entity_data in (
                    entities if isinstance(entities, list) else [entities]
                )
            ]
            return [
                await generate_entity_from_port_yaml(entity_data, project, ref)
                for entity_data in raw_entities
            ]
        except ParserError as exec:
            logger.error(
                f"Failed to parse gitops entities from gitlab project {project.path_with_namespace},z file {file_path}."
                f"\n {exec}"
            )
        except Exception:
            logger.error(
                f"Failed to get gitops entities from gitlab project {project.path_with_namespace}, file {file_path}"
            )
        return []

    async def _get_entities_by_commit(
        self, project: Project, spec: str | List["str"], commit: str, ref: str
    ) -> List[Entity]:
        logger.info(
            f"Getting entities for project {project.path_with_namespace} in path {spec} at commit {commit} and ref {ref}"
        )
        return await self._get_entities_from_git(project, spec, commit, ref)

    def should_run_for_path(self, path: str) -> bool:
        return any(does_pattern_apply(mapping, path) for mapping in self.group_mapping)

    def should_run_for_group(self, group: Group) -> bool:
        return self.should_run_for_path(group.full_path)

    def should_run_for_project(
        self,
        project: Project,
    ) -> bool:
        return self.should_run_for_path(project.path_with_namespace)

    def should_run_for_merge_request(
        self,
        merge_request: typing.Union[MergeRequest, GroupMergeRequest],
    ) -> bool:
        project_path = merge_request.references.get("full").rstrip(
            merge_request.references.get("short")
        )
        return self.should_run_for_path(project_path)

    def should_run_for_issue(
        self,
        issue: Issue,
    ) -> bool:
        project_path = issue.references.get("full").rstrip(
            issue.references.get("short")
        )
        return self.should_run_for_path(project_path)

    def should_process_project(
        self, project: Project, repos: Optional[List[str]]
    ) -> bool:
        # If `repos` selector is None or empty, we process all projects
        if not repos:
            return True
        return project.name in repos

    async def get_root_groups(self) -> List[Group]:
        groups: list[RESTObject] = []
        async for groups_batch in AsyncFetcher.fetch_batch(
            self.gitlab_client.groups.list, retry_transient_errors=True
        ):
            groups_batch = typing.cast(List[RESTObject], groups_batch)
            groups.extend(groups_batch)

        return typing.cast(
            List[Group], [group for group in groups if group.parent_id is None]
        )

    async def filter_groups_by_paths(self, groups_full_paths: list[str]) -> List[Group]:
        groups: list[RESTObject] = []

        async for groups_batch in AsyncFetcher.fetch_batch(
            self.gitlab_client.groups.list, retry_transient_errors=True
        ):
            groups_batch = typing.cast(List[RESTObject], groups_batch)
            groups.extend(groups_batch)

        return typing.cast(
            List[Group],
            [
                group
                for group in groups
                if group.attributes["full_path"] in groups_full_paths
            ],
        )

    async def get_filtered_groups_for_webhooks(
        self,
        groups_hooks_override_list: list[str] | None,
    ) -> List[Group]:
        groups_for_webhooks = []
        if groups_hooks_override_list is not None:
            if groups_hooks_override_list:
                logger.info(
                    f"Getting all the specified groups in the mapping for a token to create their webhooks for: {groups_hooks_override_list}"
                )
                groups_for_webhooks = await self.filter_groups_by_paths(
                    groups_hooks_override_list
                )

                groups_paths_not_found = [
                    group_path
                    for group_path in groups_hooks_override_list
                    if group_path
                    not in [
                        group.attributes["full_path"] for group in groups_for_webhooks
                    ]
                ]

                if groups_paths_not_found:
                    logger.warning(
                        "Some groups where not found in gitlab to create webhooks for, "
                        "probably because of groups that are not under the token's scope, or a mismatched "
                        "groups full_path in tokenGroupHooksOverrideMapping with the groups full_path in gitlab. "
                        f"full_paths of groups that where not found: {groups_paths_not_found}"
                    )
        else:
            logger.info("Getting all the root groups to create their webhooks")
            root_groups = await self.get_root_groups()
            groups_for_webhooks = [
                group
                for group in root_groups
                if any(
                    does_pattern_apply(
                        mapping.split("/")[0], group.attributes["full_path"]
                    )
                    for mapping in self.group_mapping
                )
            ]

        return groups_for_webhooks

    async def create_webhook(
        self, group: Group, events: list[str] | None
    ) -> str | None:
        logger.info(f"Creating webhook for the group: {group.attributes['full_path']}")

        group_id = group.get_id()

        if group_id is None:
            logger.info(f"Group {group.attributes['full_path']} has no id. skipping...")
            return None
        else:
            hook = await self._get_webhook_for_group(group)
            if hook:
                logger.info(f"Webhook already exists for group {group.get_id()}")

                if hook.alert_status == "disabled":
                    logger.info(
                        f"Webhook exists for group {group.get_id()} but is disabled, deleting and re-creating..."
                    )
                    await self._delete_group_webhook(group, hook.id)
                    await self._create_group_webhook(group, events)
                    logger.info(f"Webhook re-created for group {group.get_id()}")
            else:
                await self._create_group_webhook(group, events)

        return str(group_id)

    def create_system_hook(self) -> None:
        logger.info("Checking if system hook already exists")
        try:
            for hook in self.gitlab_client.hooks.list(iterator=True):
                if hook.url == f"{self.app_host}/integration/system/hook":
                    logger.info("System hook already exists, no need to create")
                    return
        except Exception:
            logger.error(
                "Failed to check if system hook exists, skipping trying to create, to avoid duplicates"
            )
            return

        logger.info("Creating system hook")
        try:
            resp = self.gitlab_client.hooks.create(
                {
                    "url": f"{self.app_host}/integration/system/hook",
                    "push_events": True,
                    "merge_requests_events": True,
                    "repository_update_events": False,
                }
            )
            logger.info(f"Created system hook with id {resp.get_id()}")
        except Exception:
            logger.error("Failed to create system hook")

    async def get_project(self, project_id: int) -> Project | None:
        """
        Returns project if it should be processed, None otherwise
        If the project is not in the cache, it will be fetched from gitlab and validated against the group mapping
        before being added to the cache
        :param project_id: project id
        :return: Project if it should be processed, None otherwise
        """
        logger.info(f"fetching project {project_id}")
        filtered_projects = event.attributes.setdefault(
            PROJECTS_CACHE_KEY, {}
        ).setdefault(self.gitlab_client.private_token, {})

        if project := filtered_projects.get(project_id):
            return project

        project = await AsyncFetcher.fetch_single(
            self.gitlab_client.projects.get, project_id
        )
        if self.should_run_for_project(project):
            event.attributes[PROJECTS_CACHE_KEY][self.gitlab_client.private_token][
                project_id
            ] = project
            return project
        else:
            return None

    async def get_group(self, group_id: int) -> Optional[Group]:
        try:
            logger.info(f"Fetching group with ID: {group_id}")
            group = await AsyncFetcher.fetch_single(
                self.gitlab_client.groups.get, group_id
            )
            if isinstance(group, Group) and self.should_run_for_group(group):
                return group
            else:
                return None
        except gitlab.exceptions.GitlabGetError as err:
            if err.response_code == 404:
                logger.warning(f"Group with ID {group_id} not found (404).")
                return None
            else:
                logger.error(f"Failed to fetch group with ID {group_id}: {err}")
                raise

    async def get_all_groups(
        self, skip_validation: bool = False
    ) -> typing.AsyncIterator[List[Group]]:
        logger.info("fetching all groups for the token")

        async for groups_batch in AsyncFetcher.fetch_batch(
            fetch_func=self.gitlab_client.groups.list,
            validation_func=(
                self.should_run_for_group if not (skip_validation) else None
            ),
            pagination="offset",
            order_by="id",
            sort="asc",
        ):
            groups: List[Group] = typing.cast(List[Group], groups_batch)
            logger.info(
                f"Queried {len(groups)} groups {[group.path for group in groups]}"
            )
            yield groups

    async def get_all_root_groups(self) -> typing.AsyncIterator[List[Group]]:
        logger.info("fetching all root groups for the token")

        def is_root_group(group: Group) -> bool:
            return group.parent_id is None

        async for groups_batch in AsyncFetcher.fetch_batch(
            fetch_func=self.gitlab_client.groups.list,
            validation_func=is_root_group,
            pagination="offset",
            order_by="id",
            sort="asc",
        ):
            groups: List[Group] = typing.cast(List[Group], groups_batch)
            logger.info(
                f"Queried {len(groups)} root groups {[group.path for group in groups]}"
            )
            yield groups

    async def get_all_projects(self) -> typing.AsyncIterator[List[Project]]:
        logger.info("fetching all projects for the token")
        port_app_config: GitlabPortAppConfig = typing.cast(
            "GitlabPortAppConfig", event.port_app_config
        )

        cached_projects = event.attributes.setdefault(
            PROJECTS_CACHE_KEY, {}
        ).setdefault(self.gitlab_client.private_token, {})

        if cached_projects:
            yield cached_projects.values()
            return

        async for projects_batch in AsyncFetcher.fetch_batch(
            fetch_func=self.gitlab_client.projects.list,
            validation_func=self.should_run_for_project,
            include_subgroups=True,
            owned=port_app_config.filter_owned_projects,
            visibility=port_app_config.project_visibility_filter,
            pagination="offset",
            order_by="id",
            sort="asc",
        ):
            if projects_batch:
                projects: List[Project] = typing.cast(List[Project], projects_batch)
                logger.info(
                    f"Queried {len(projects)} projects {[project.path_with_namespace for project in projects]}"
                )
                cached_projects = event.attributes[PROJECTS_CACHE_KEY][
                    self.gitlab_client.private_token
                ]
                cached_projects.update({project.id: project for project in projects})
                yield projects
            else:
                logger.info("No valid projects found for the token in the current page")

    @classmethod
    async def async_project_labels_wrapper(cls, project: Project) -> dict[str, Any]:
        try:
            all_labels = [
                label.attributes
                async for labels_batch in AsyncFetcher.fetch_batch(
                    fetch_func=project.labels.list
                )
                for label in typing.cast(List[ProjectLabel], labels_batch)
            ]

            return {"__labels": all_labels}
        except Exception as e:
            logger.warning(
                f"Failed to get labels for project={project.path_with_namespace}. error={e}"
            )
            return {"__labels": []}

    @classmethod
    async def async_project_language_wrapper(cls, project: Project) -> dict[str, Any]:
        try:
            languages = await anyio.to_thread.run_sync(project.languages)
            return {"__languages": languages}
        except Exception as e:
            logger.warning(
                f"Failed to get languages for project={project.path_with_namespace}. error={e}"
            )
            return {"__languages": {}}

    @classmethod
    async def enrich_project_with_extras(
        cls, project: Project, include_labels: bool = False
    ) -> Project:
        if include_labels:
            tasks = [
                cls.async_project_language_wrapper(project),
                cls.async_project_labels_wrapper(project),
            ]
        else:
            tasks = [cls.async_project_language_wrapper(project)]
        tasks_extras = await asyncio.gather(*tasks)
        for task_extras in tasks_extras:
            for key, value in task_extras.items():
                setattr(project, key, value)  # Update the project object
        return project

    @staticmethod
    def validate_file_is_directory(
        file: Union[RESTObject, dict[str, Any], Project]
    ) -> bool:
        if isinstance(file, dict):
            return file["type"] == "tree"
        return False

    async def get_all_folders_in_project_path(
        self, project: Project, folder_selector
    ) -> typing.AsyncIterator[List[dict[str, Any]]]:
        branch = folder_selector.branch or project.default_branch
        try:
            async for repository_tree_batch in AsyncFetcher.fetch_batch(
                fetch_func=project.repository_tree,
                validation_func=self.validate_file_is_directory,
                path=folder_selector.path,
                ref=branch,
            ):
                repository_tree_files: List[dict[str, Any]] = typing.cast(
                    List[dict[str, Any]], repository_tree_batch
                )
                logger.info(
                    f"Found {len(repository_tree_files)} folders {[folder['path'] for folder in repository_tree_files]}"
                    f" in project {project.path_with_namespace}"
                )
                yield [
                    {
                        "folder": folder,
                        "repo": project.asdict(),
                        "__branch": branch,
                    }
                    for folder in repository_tree_files
                ]
        except Exception as e:
            logger.error(
                f"Failed to get folders in project={project.path_with_namespace} for path={folder_selector.path} and "
                f"branch={branch}. error={e}"
            )
            return

    async def get_all_jobs(
        self, project: Project
    ) -> typing.AsyncIterator[List[ProjectPipelineJob]]:
        def should_run_for_job(_: Union[RESTObject, dict[str, Any], Project]) -> bool:
            return True

        logger.info(f"fetching jobs for project {project.path_with_namespace}")
        async for pipeline_jobs_batch in AsyncFetcher.fetch_batch(
            fetch_func=project.jobs.list,
            validation_func=should_run_for_job,
            pagination="offset",
            order_by="id",
            sort="asc",
        ):
            pipeline_jobs = typing.cast(List[ProjectPipelineJob], pipeline_jobs_batch)

            logger.info(
                f"Queried {len(pipeline_jobs)} jobs {[job.name for job in pipeline_jobs]}"
            )
            yield pipeline_jobs

    async def get_all_pipelines(
        self, project: Project
    ) -> typing.AsyncIterator[List[ProjectPipeline]]:
        from_time = datetime.now() - timedelta(days=14)
        created_after = from_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        def should_run_for_pipeline(
            _: Union[RESTObject, dict[str, Any], Project]
        ) -> bool:
            return True

        logger.info(
            f"Fetching pipelines for project {project.path_with_namespace} created after {created_after}"
        )
        async for pipelines_batch in AsyncFetcher.fetch_batch(
            fetch_func=project.pipelines.list,
            validation_func=should_run_for_pipeline,
            pagination="offset",
            order_by="id",
            sort="asc",
            created_after=created_after,
        ):
            pipelines = typing.cast(List[ProjectPipeline], pipelines_batch)
            logger.info(
                f"Queried {len(pipelines)} pipelines {[pipeline.id for pipeline in pipelines]}"
            )
            yield pipelines

    async def get_opened_merge_requests(
        self, group: Group
    ) -> typing.AsyncIterator[List[MergeRequest]]:
        async for merge_request_batch in AsyncFetcher.fetch_batch(
            fetch_func=group.mergerequests.list,
            validation_func=self.should_run_for_merge_request,
            pagination="offset",
            order_by="created_at",
            sort="desc",
            state="opened",
        ):
            merge_requests: List[MergeRequest] = typing.cast(
                List[MergeRequest], merge_request_batch
            )
            yield merge_requests

    async def get_closed_merge_requests(
        self, group: Group, updated_after: datetime
    ) -> typing.AsyncIterator[List[MergeRequest]]:
        async for merge_request_batch in AsyncFetcher.fetch_batch(
            fetch_func=group.mergerequests.list,
            validation_func=self.should_run_for_merge_request,
            pagination="offset",
            order_by="created_at",
            sort="desc",
            state=["closed", "locked", "merged"],
            updated_after=updated_after.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        ):
            merge_requests: List[MergeRequest] = typing.cast(
                List[MergeRequest], merge_request_batch
            )
            yield merge_requests

    async def get_all_issues(self, group: Group) -> typing.AsyncIterator[List[Issue]]:
        async for issues_batch in AsyncFetcher.fetch_batch(
            fetch_func=group.issues.list,
            validation_func=self.should_run_for_issue,
            pagination="offset",
            order_by="created_at",
            sort="desc",
        ):
            issues: List[Issue] = typing.cast(List[Issue], issues_batch)
            yield issues

    def should_run_for_members(self, include_bot_members: bool, member: RESTObject):
        return include_bot_members or not member.username.__contains__("bot")

    async def enrich_object_with_members(
        self,
        obj: RESTObject,
        include_inherited_members: bool = False,
        include_bot_members: bool = True,
        include_verbose_member_object: bool = False,
    ) -> RESTObject:
        """
        Enriches an object (e.g., Project or Group) with its members.
        """
        obj_name = obj.name
        logger.info(f"Starting member enrichment for {obj.name}")

        setattr(obj, "__members", [])
        members_list = getattr(obj, "__members")

        processed_member_ids: Set[int] = set()
        total_members_processed = 0

        try:
            async for members_batch in self.get_all_object_members(
                obj, include_inherited_members, include_bot_members
            ):
                # Filter out duplicates
                for member in members_batch:
                    member_id = member.id
                    if member_id not in processed_member_ids:
                        processed_member_ids.add(member_id)
                        if include_verbose_member_object:
                            members_list.append(member.asdict())
                        else:
                            members_list.append(
                                {
                                    "id": member.id,
                                    "username": member.username,
                                    "email": getattr(member, "email", ""),
                                }
                            )
                total_members_processed += len(members_batch)

                logger.info(
                    f"Processed {total_members_processed} members for {obj_name}"
                )

            logger.info(
                f"Completed member enrichment for {obj_name} with {len(members_list)} unique members"
            )
            return obj

        except Exception as e:
            logger.error(f"Error enriching members for {obj_name}: {e}")
            return obj

    async def get_all_object_members(
        self,
        obj: RESTObject,
        include_inherited_members: bool = False,
        include_bot_members: bool = True,
        page_size: int = 50,
    ) -> AsyncIterator[List[RESTObject]]:
        """
        Fetches all members of an object (e.g., Project or Group) generically.
        """
        obj_name = getattr(obj, "name", "unknown")
        try:
            logger.info(
                f"Fetching members of {obj_name} with pagination size {page_size}"
            )

            members_attr = "members_all" if include_inherited_members else "members"
            members_manager = getattr(obj, members_attr, None)
            if not members_manager:
                raise AttributeError(f"Object does not have attribute '{members_attr}'")

            validation_func = functools.partial(
                self.should_run_for_members, include_bot_members
            )

            async for members_batch in AsyncFetcher.fetch_batch(
                fetch_func=members_manager.list,
                validation_func=validation_func,
                pagination="page",
                page_size=page_size,
                order_by="id",
                sort="asc",
            ):
                members: List[RESTObject] = typing.cast(List[RESTObject], members_batch)
                logger.info(f"Fetched page with {len(members)} members for {obj_name}")
                yield members

        except Exception as e:
            logger.error(f"Failed to get members for object='{obj_name}'. Error: {e}")
            return

    async def get_entities_diff(
        self,
        project: Project,
        spec_path: str | List[str],
        before: str,
        after: str,
        ref: str,
    ) -> Tuple[List[Entity], List[Entity]]:
        logger.info(
            f'Getting entities diff for project {project.path_with_namespace}, in path "{spec_path}", before {before},'
            f" after {after}, ref {ref}"
        )
        entities_before = await self._get_entities_by_commit(
            project, spec_path, before, ref
        )

        logger.info(f"Found {len(entities_before)} entities in the previous state")

        entities_after = await self._get_entities_by_commit(
            project, spec_path, after, ref
        )

        logger.info(f"Found {len(entities_after)} entities in the current state")

        return entities_before, entities_after

    async def _parse_file_content(
        self, project: Project, file: ProjectFile
    ) -> Union[str, dict[str, Any], list[Any]] | None:
        """
        Process a file from a project. If the file is a JSON or YAML, it will be parsed, otherwise the raw content will be returned
        :param file: file object
        :return: parsed content of the file
        """
        if file.size > MAX_ALLOWED_FILE_SIZE_IN_BYTES:
            logger.warning(
                f"File {file.file_path} in {project.path_with_namespace} is too large to be processed. "
                f"Maximum size allowed is 1MB. Actual size of file: {file.size}"
            )
            return None
        if file.file_name.endswith(JSON_SUFFIX):
            try:
                return await anyio.to_thread.run_sync(json.loads, file.decode())
            except json.JSONDecodeError:
                logger.debug(
                    f"Failed to parse file {file.file_path} in project {project.path_with_namespace} as JSON,"
                    f" returning raw content"
                )
                return file.decode().decode("utf-8")
        elif file.file_name.endswith(YAML_SUFFIX):
            try:
                logger.debug(
                    f"Trying to process file {file.file_path} in project {project.path_with_namespace} as YAML"
                )
                documents = list(
                    await anyio.to_thread.run_sync(
                        yaml.load_all, file.decode(), yaml.SafeLoader
                    )
                )
                if not documents:
                    logger.debug(
                        f"Failed to parse file {file.file_path} in project {project.path_with_namespace} as YAML,"
                        f" returning raw content"
                    )
                    return file.decode().decode("utf-8")
                return documents if len(documents) > 1 else documents[0]
            except yaml.YAMLError:
                logger.debug(
                    f"Failed to parse file {file.file_path} in project {project.path_with_namespace} as YAML,"
                    f" returning raw content"
                )
                return file.decode().decode("utf-8")
        else:
            logger.debug(
                f"File {file.file_path} in project {project.path_with_namespace} is not a JSON or YAML file,"
                f" returning raw content"
            )
            return file.decode().decode("utf-8")

    async def get_and_parse_single_file(
        self, project: Project, file_path: str, branch: str
    ) -> dict[str, Any] | None:
        try:
            logger.info(
                f"Processing file {file_path} in project {project.path_with_namespace}"
            )
            project_file = await AsyncFetcher.fetch_single(
                project.files.get, file_path, branch
            )
            logger.info(
                f"Fetched file {file_path} in project {project.path_with_namespace}"
            )
            project_file = typing.cast(ProjectFile, project_file)
            parsed_file = await self._parse_file_content(project, project_file)
            project_file_dict = project_file.asdict()

            if not parsed_file:
                # if the file is too large to be processed, we return None
                return None

            # Update the content with the parsed content. Useful for JSON and YAML files that can be further processed using itemsToParse
            project_file_dict["content"] = parsed_file

            return {"file": project_file_dict, "repo": project.asdict()}
        except Exception as e:
            logger.error(
                f"Failed to process file {file_path} in project {project.path_with_namespace}. error={e}"
            )
            return None
