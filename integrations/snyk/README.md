# Snyk

Snyk targets, projects and vulnerabilities integration for Port using Port-Ocean Framework

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Installation
For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration at your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.secrets.token: Your Snyk API token
# integration.secrets.webhookSecret: This field is optional. It is a password you create, that Snyk uses to ensure the webhook notification is authenticated
# integration.config.appHost: Your Snyk app host (optional)
# integration.config.apiUrl: The url of the Snyk API. If not specified, the default will be https://api.snyk.io
# integration.config.organizationId: The Snyk organization ID

helm upgrade --install my-snyk-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-snyk-integration"  \
	--set integration.type="snyk"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.secrets.token="<your-token>"  \
  --set integration.config.organizationId="<your-organization-id>"  \
  --set ingress.enabled=true  \
  --set ingress.annotations."nginx\.ingress\.kubernetes\.io/rewrite-target"= / 
```

## Supported Kinds

### Target
This kind represents a Snyk target. The schema should be similar to the one on the [Snyk REST API documentation](https://apidocs.snyk.io/?version=2023-08-21%7Ebeta#tag--Targets).
To bring this data the integration is using the Snyk REST API in version 2021-08-21-beta.


<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "snykTarget",
    "title": "Snyk Target",
    "icon": "Snyk",
    "schema": {
        "properties": {
            "criticalOpenVulnerabilities": {
                "icon": "Vulnerability",
                "type": "number",
                "title": "Open Critical Vulnerabilities"
            },
            "highOpenVulnerabilities": {
                "icon": "Vulnerability",
                "type": "number",
                "title": "Open High Vulnerabilities"
            },
            "mediumOpenVulnerabilities": {
                "icon": "Vulnerability",
                "type": "number",
                "title": "Open Medium Vulnerabilities"
            },
            "lowOpenVulnerabilities": {
                "icon": "Vulnerability",
                "type": "number",
                "title": "Open Low Vulnerabilities"
            },
            "origin": {
                "title": "Target Origin",
                "type": "string",
                "enum": [
                    "artifactory-cr",
                    "aws-config",
                    "aws-lambda",
                    "azure-functions",
                    "azure-repos",
                    "bitbucket-cloud",
                    "bitbucket-server",
                    "cli",
                    "cloud-foundry",
                    "digitalocean-cr",
                    "docker-hub",
                    "ecr",
                    "gcr",
                    "github",
                    "github-cr",
                    "github-enterprise",
                    "gitlab",
                    "gitlab-cr",
                    "google-artifact-cr",
                    "harbor-cr",
                    "heroku",
                    "ibm-cloud",
                    "kubernetes",
                    "nexus-cr",
                    "pivotal",
                    "quay-cr",
                    "terraform-cloud"
                ]
            }
        },
        "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
        "snykProjects": {
            "title": "Snyk Projects",
            "target": "snykProject",
            "required": false,
            "many": true
        }
    }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: target
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .attributes.displayName
          title: .attributes.displayName
          blueprint: '"snykTarget"'
          properties:
            origin: .attributes.origin
            highOpenVulnerabilities: '[.__projects[].meta.latest_issue_counts.high] | add'
            mediumOpenVulnerabilities: '[.__projects[].meta.latest_issue_counts.medium] | add'
            lowOpenVulnerabilities: '[.__projects[].meta.latest_issue_counts.low] | add'
            criticalOpenVulnerabilities: '[.__projects[].meta.latest_issue_counts.critical] | add'
          relations:
            snykProjects: '[.__projects[].id]'
```
</details>

### Project
This kind represents a Snyk project. The schema should be similar to the one on the [Snyk REST API documentation](https://apidocs.snyk.io/?version=2023-08-21#tag--Projects). The owner and importer details are fetched from the [Snyk v1 API documentation](https://snyk.docs.apiary.io/#reference/users/user-details/get-user-details)
To bring this data the integration is using the Snyk REST API in version 2021-08-21.

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "snykProject",
    "title": "Snyk Project",
    "icon": "Snyk",
    "schema": {
        "properties": {
            "url": {
                "type": "string",
                "title": "URL",
                "format": "url",
                "icon": "Snyk"
            },
            "owner": {
                "type": "string",
                "title": "Owner",
                "format": "user",
                "icon": "TwoUsers"
            },
            "businessCriticality": {
                "title": "Business Criticality",
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "critical",
                        "high",
                        "medium",
                        "low"
                    ]
                },
                "icon": "DefaultProperty"
            },
            "environment": {
                "items": {
                    "type": "string",
                    "enum": [
                        "frontend",
                        "backend",
                        "internal",
                        "external",
                        "mobile",
                        "saas",
                        "onprem",
                        "hosted",
                        "distributed"
                    ]
                },
                "icon": "Environment",
                "title": "Environment",
                "type": "array"
            },
            "lifeCycle": {
                "title": "Life Cycle",
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "development",
                        "sandbox",
                        "production"
                    ]
                },
                "icon": "DefaultProperty"
            },
            "highOpenVulnerabilities": {
                "icon": "Vulnerability",
                "type": "number",
                "title": "Open High Vulnerabilities"
            },
            "mediumOpenVulnerabilities": {
                "icon": "Vulnerability",
                "type": "number",
                "title": "Open Medium Vulnerabilities"
            },
            "lowOpenVulnerabilities": {
                "icon": "Vulnerability",
                "type": "number",
                "title": "Open Low Vulnerabilities"
            },
            "importedBy": {
                "icon": "TwoUsers",
                "type": "string",
                "title": "Imported By",
                "format": "user"
            },
            "tags": {
                "type": "array",
                "title": "Tags",
                "icon": "DefaultProperty"
            }
        },
        "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
        "snykVulnerabilities": {
            "title": "Snyk Vulnerabilities",
            "target": "snykVulnerability",
            "required": false,
            "many": true
        }
    }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: project
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          title: .attributes.name
          blueprint: '"snykProject"'
          properties:
            url: ("https://app.snyk.io/org/" + .relationships.organization.data.id + "/project/" + .id | tostring)
            owner: .__owner.email
            businessCriticality: .attributes.business_criticality
            environment: .attributes.environment
            lifeCycle: .attributes.lifecycle
            highOpenVulnerabilities: .meta.latest_issue_counts.high
            mediumOpenVulnerabilities: .meta.latest_issue_counts.medium
            lowOpenVulnerabilities: .meta.latest_issue_counts.low
            criticalOpenVulnerabilities: .meta.latest_issue_counts.critical
            importedBy: .__importer.email
            tags: .attributes.tags
          relations:
            snykVulnerabilities: '[.__issues[] | select(.issueType == "vuln").issueData.id]'
```
</details>

### Issue
This kind represents a Snyk vulnerability or issues. The schema should be similar to the one on the [Snyk V1 API documentation](https://snyk.docs.apiary.io/#reference/projects/aggregated-project-issues/list-all-aggregated-issues).
To bring this data the integration is using the Snyk v1 API.

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "snykVulnerability",
    "title": "Snyk Vulnerability",
    "icon": "Snyk",
    "schema": {
        "properties": {
            "score": {
                "icon": "Star",
                "type": "number",
                "title": "Score"
            },
            "packageName": {
                "type": "string",
                "title": "Package Name",
                "icon": "DefaultProperty"
            },
            "packageVersions": {
                "icon": "Package",
                "title": "Package Versions",
                "type": "array"
            },
            "type": {
                "type": "string",
                "title": "Type",
                "enum": [
                    "vuln",
                    "license",
                    "configuration"
                ],
                "icon": "DefaultProperty"
            },
            "severity": {
                "icon": "Alert",
                "title": "Issue Severity",
                "type": "string",
                "enum": [
                    "low",
                    "medium",
                    "high",
                    "critical"
                ],
                "enumColors": {
                    "low": "green",
                    "medium": "yellow",
                    "high": "red",
                    "critical": "red"
                }
            },
            "url": {
                "icon": "Link",
                "type": "string",
                "title": "Issue URL",
                "format": "url"
            },
            "language": {
                "type": "string",
                "title": "Language",
                "icon": "DefaultProperty"
            },
            "publicationTime": {
                "type": "string",
                "format": "date-time",
                "title": "Publication Time",
                "icon": "DefaultProperty"
            },
            "isPatched": {
                "type": "boolean",
                "title": "Is Patched",
                "icon": "DefaultProperty"
            }
        },
        "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {}
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: issue
    selector:
      query: '.issueType == "vuln"'
    port:
      entity:
        mappings:
          identifier: .issueData.id
          title: .issueData.title
          blueprint: '"snykVulnerability"'
          properties:
            score: .priorityScore
            packageName: .pkgName
            packageVersions: .pkgVersions
            type: .issueType
            severity: .issueData.severity
            url: .issueData.url
            language: .issueData.language // .issueType
            publicationTime: .issueData.publicationTime
            isPatched: .isPatched
```
</details>

## Installation

```sh
make install
```

## Runnning Localhost
```sh
make run
```
or
```sh
ocean sail
```

## Running Tests

`make test`

## Access Swagger Documentation

> <http://localhost:8080/docs>

## Access Redoc Documentation

> <http://localhost:8080/redoc>


## Folder Structure
The Snyk integration suggested folder structure is as follows:

```
snyk/
├─ snyk/             # The integration logic
│  ├─ client.py      # Wrapper to the Snyk REST API and other custom integration logic
├─ main.py              # The main exports the custom Ocean logic to the ocean sail command
├─ pyproject.toml
└─ Dockerfile
```