from typing import List, Tuple

import yaml
from gitlab import Gitlab
from gitlab.v4.objects import Group
from loguru import logger

from gitlabapp.core.entities import generate_entity_from_port_yaml
from gitlabapp.core.utils import does_pattern_apply
from gitlabapp.models.gitlab import HookContext, ScopeType, Scope
from port_ocean.core.models import Entity


class GitlabService:
    def __init__(
        self,
        gitlab_client: Gitlab,
        app_host: str,
        group_mapping: List[str],
    ):
        self.gitlab_client = gitlab_client
        self.app_host = app_host
        self.group_mapping = group_mapping

    def _is_exists(self, group: Group) -> bool:
        for hook in group.hooks.list(iterator=True):
            if hook.url == f"{self.app_host}/integration/hook/{group.get_id()}":
                return True
        return False

    def _create_group_webhook(self, group: Group):
        group.hooks.create(
            {
                "url": f"{self.app_host}/integration/hook/{group.get_id()}",
                "push_events": True,
                "merge_requests_events": True,
            }
        )

        return group.get_id()

    def get_root_groups(self) -> List[Group]:
        groups = self.gitlab_client.groups.list(iterator=True)
        return [group for group in groups if group.parent_id is None]

    def create_webhooks(self):
        root_partial_groups = self.get_root_groups()
        filtered_partial_groups = [
            group
            for group in root_partial_groups
            if any(
                does_pattern_apply(mapping.split("/")[0], group.attributes["full_path"])
                for mapping in self.group_mapping
            )
        ]

        webhook_ids = []
        for partial_group in filtered_partial_groups:
            if self._is_exists(partial_group):
                logger.info(
                    f"Webhook already exists for group {partial_group.get_id()}"
                )
            else:
                self._create_group_webhook(partial_group)
            webhook_ids.append(partial_group.get_id())

        return webhook_ids

    def _filter_mappings(self, projects):
        return [
            project
            for project in projects
            if all(
                does_pattern_apply(mapping, project["path_with_namespace"])
                for mapping in self.group_mapping
            )
        ]

    def get_group_projects(self, group_id: int | None = None):
        if group_id is None:
            return [
                project
                for group in self.gitlab_client.groups.list()
                for project in self.gitlab_client.groups.get(group.id).attributes[
                    "projects"
                ]
            ]
        group = self.gitlab_client.groups.get(group_id)
        return [
            *group.attributes["projects"],
            *[
                self.get_group_projects(sub_group.id)
                for sub_group in group.subgroups.list()
            ],
        ]

    def get_projects_by_scope(self, scope: Scope | None = None):
        if scope and scope.type == ScopeType.Project:
            logger.info(f"fetching project {scope.id}")
            project = self.gitlab_client.projects.get(scope.id)
            return self._filter_mappings([project.asdict()])

        if scope and scope.type == ScopeType.Group:
            logger.info(f"fetching all projects for group {scope.id}")
            projects = self.get_group_projects(scope.id)
        else:
            logger.info("fetching all projects for the token")
            projects = self.get_group_projects()

        return self._filter_mappings(projects)

    def _get_changed_files_between_commits(self, project_id: int, head: str):
        project = self.gitlab_client.projects.get(project_id)
        return project.commits.get(head).diff()

    def validate_config_changed(self, context: HookContext):
        changed_files = self._get_changed_files_between_commits(
            context.project.id, context.after
        )
        has_changed = bool(
            [
                file["new_path"]
                for file in changed_files
                if file["new_path"] == ".gitlab/port-app-config.yml"
            ]
        )
        scope = Scope(ScopeType.Project, context.project.id)
        if context.project.name == "gitlab-private":
            project = self.gitlab_client.projects.get(context.project.id)
            scope = Scope(ScopeType.Group, project.namespace["id"])
        return has_changed, scope

    def _get_file_paths(
        self, context: HookContext, path: str | List[str], commit_sha: str
    ):
        project = self.gitlab_client.projects.get(context.project.id)
        if not isinstance(path, list):
            path = [path]
        files = project.repository_tree(ref=commit_sha, all=True)
        return [
            file["path"]
            for file in files
            if does_pattern_apply(path, file["path"] or "")
        ]

    def _get_entities_from_git(
        self, context: HookContext, file_name: str, sha: str, ref: str
    ) -> List[Entity]:
        try:
            file_content = self.gitlab_client.projects.get(
                context.project.id
            ).files.get(file_path=file_name, ref=sha)
            # ToDo: add validation for port yml
            # validate_port_yml()
            # todo: log on failed yml loading
            entities = yaml.safe_load(file_content.decode())
            raw_entities = [
                Entity(**entity_data)
                for entity_data in (
                    entities if isinstance(entities, list) else [entities]
                )
            ]
            return [
                generate_entity_from_port_yaml(
                    entity_data, context, self.gitlab_client, ref
                )
                for entity_data in raw_entities
            ]
        except Exception as e:
            return []

    def _get_entities_by_commit(
        self, context: HookContext, spec: str | List["str"], commit: str, ref: str
    ) -> List[Entity]:
        spec_paths = self._get_file_paths(context, spec, commit)
        return [
            entity
            for path in spec_paths
            for entity in self._get_entities_from_git(context, path, commit, ref)
        ]

    def get_entities_diff(
        self,
        context: HookContext,
        spec_path: str | List[str],
        before: str,
        after: str,
        ref: str,
    ) -> Tuple[List[Entity], List[Entity]]:
        entities_before = self._get_entities_by_commit(context, spec_path, before, ref)
        entities_after = self._get_entities_by_commit(context, spec_path, after, ref)

        return entities_before, entities_after
