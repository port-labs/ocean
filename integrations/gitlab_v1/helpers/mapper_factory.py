from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseMapper(ABC):
    endpoint: str = ""

    @abstractmethod
    def get_query_params(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def map(self, item: Dict[str, Any]) -> Dict[str, Any]:
        pass

class GroupMapper(BaseMapper):
    endpoint = "groups"

    def get_query_params(self):
        return {
            "min_access_level": 50,
            "order_by": "name",
            "sort": "asc"
        }

    def map(self, group):
        return {
            "identifier": str(group["id"]),
            "title": group["name"],
            "blueprint": "gitlabGroup",
            "properties": {
                "fullPath": group["full_path"],
                "visibility": group["visibility"],
                "description": group.get("description", ""),
                "webUrl": group["web_url"],
                "avatarUrl": group.get("avatar_url", ""),
                "createdAt": group["created_at"],
                "lastActivityAt": group.get("last_activity_at"),
                "memberCount": group.get("member_count", 0),
                "parentId": str(group["parent_id"]) if group.get("parent_id") else None
            }
        }

class ProjectMapper(BaseMapper):
    endpoint = "projects"

    def get_query_params(self):
        return {
            "membership": True,
            "order_by": "name",
            "sort": "asc"
        }

    def map(self, project):
        return {
            "identifier": str(project["id"]),
            "title": project["name"],
            "blueprint": "gitlabProject",
            "properties": {
                "fullPath": project["path_with_namespace"],
                "visibility": project["visibility"],
                "description": project.get("description", ""),
                "webUrl": project["web_url"],
                "avatarUrl": project.get("avatar_url", ""),
                "createdAt": project["created_at"],
                "lastActivityAt": project.get("last_activity_at"),
                "defaultBranch": project.get("default_branch", "main"),
                "archived": project.get("archived", False),
                "topics": project.get("topics", []),
                "forksCount": project.get("forks_count", 0),
                "starCount": project.get("star_count", 0)
            },
            "relations": {
                "group": [{
                    "target": str(project["namespace"]["id"]),
                    "blueprint": "gitlabGroup"
                }]
            }
        }

class MergeRequestMapper(BaseMapper):
    endpoint = "merge_requests"

    def get_query_params(self):
        return {
            "scope": "all",
            "order_by": "created_at",
            "sort": "desc"
        }

    def map(self, mr):
        return {
            "identifier": str(mr["id"]),
            "title": mr["title"],
            "blueprint": "gitlabMergeRequest",
            "properties": {
                "creator": mr["author"]["username"],
                "status": mr["state"],
                "createdAt": mr["created_at"],
                "updatedAt": mr.get("updated_at", ""),
                "mergedAt": mr.get("merged_at", ""),
                "link": mr["web_url"],
                "reviewers": [reviewer["username"] for reviewer in mr.get("reviewers", [])]
            },
            "relations": {
                "service": [{
                    "target": str(mr["project_id"]),
                    "blueprint": "project"
                }]
            }
        }

class IssueMapper(BaseMapper):
    endpoint = "issues"

    def get_query_params(self):
        return {
            "scope": "all",
            "order_by": "created_at",
            "sort": "desc"
        }

    def map(self, issue):
        return {
            "identifier": str(issue["id"]),
            "title": issue["title"],
            "blueprint": "gitlabIssue",
            "properties": {
                "link": issue["web_url"],
                "description": issue.get("description", ""),
                "createdAt": issue["created_at"],
                "closedAt": issue.get("closed_at", ""),
                "updatedAt": issue.get("updated_at", ""),
                "creator": issue["author"]["username"],
                "status": issue["state"],
                "labels": issue.get("labels", [])
            },
            "relations": {
                "service": [{
                    "target": str(issue["project_id"]),
                    "blueprint": "project"
                }]
            }
        }

class MapperFactory:
    def get_mapper(self, resource_type: str) -> BaseMapper:
        mappers = {
            "gitlabGroup": GroupMapper(),
            "gitlabProject": ProjectMapper(),
            "gitlabMergeRequest": MergeRequestMapper(),
            "gitlabIssue": IssueMapper(),
        }
        if resource_type not in mappers:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        return mappers[resource_type]
