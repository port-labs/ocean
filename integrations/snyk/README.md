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
# integration.secrets.ApiToken: Your Snyk API token
# integration.secrets.webhookSecret: Your Snyk webhook secret. This is a password you create, that Snyk uses to ensure the webhook notification is authentic
# integration.config.appHost: Your Snyk app host
# integration.config.apiUrl: The url of the Snyk API. If not specified, the default will be https://api.snyk.io
# integration.config.organizationId: The Snyk organization ID

helm upgrade --install my-snyk-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-snyk-integration"  \
	--set integration.type="snyk"  \
	--set integration.triggerChannel.type="POLLING"  \
	--set integration.secrets.ApiToken="<your-token>"  \
    --set integration.secrets.webhookSecret="<your-secret>"  \
	--set integration.config.appHost="<your-host-url>"  \
    --set integration.config.apiUrl="<your-api-url>"  \
    --set integration.config.organizationId="<your-organization-id>"  \
     --set ingress.enabled=true  \
     --set ingress.annotations."nginx\.ingress\.kubernetes\.io/rewrite-target"= / 
```
## Supported Kinds
### Targets
This kind represents a Snyk target.

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier":"snykTarget",
    "description":"This blueprint represents a snyk target in our software catalog",
    "title":"Snyk Target",
    "icon":"Snyk",
    "schema":{
        "properties":{
            "origin":{
            "title":"Origin",
            "type":"string"
            },
            "isPrivate":{
            "title":"Is Private",
            "type":"string"
            },
            "remoteUrl":{
            "title":"Remote URL",
            "type":"string",
            "format":"url"
            }
        },
        "required":[
            
        ]
    },
    "mirrorProperties":{
        
    },
    "calculationProperties":{
        
    },
    "relations":{
        
    }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: targets
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          title: .attributes.displayName
          blueprint: '"snykTarget"'
          properties:
            origin: .attributes.origin
            isPrivate: .attributes.isPrivate | tostring
            remoteUrl: .attributes.remoteUrl

```
</details>

### Projects
This kind represents a Snyk project.

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier":"snykProject",
    "description":"This blueprint represents a snyk project in our software catalog",
    "title":"Snyk Project",
    "icon":"Snyk",
    "schema":{
        "properties":{
            "type":{
            "title":"Type",
            "type":"string"
            },
            "targetFile":{
            "title":"Target File",
            "type":"string"
            },
            "targetReference":{
            "title":"Target Reference",
            "type":"string"
            },
            "origin":{
            "title":"Origin",
            "type":"string"
            },
            "status":{
            "title":"Status",
            "type":"string",
            "enum": ["active", "inactive"]
            },
            "createdAt":{
            "title":"Create At",
            "type":"string",
            "format":"date-time"
            },
            "tags":{
            "type":"array",
            "items":{
                "type":"string"
            },
            "title":"Tags"
            },
            "businessCriticality":{
            "title":"Business Criticality",
            "type":"array"
            },
            "environment":{
            "title":"Environment",
            "type":"array"
            }
        },
        "required":[
            
        ]
    },
    "mirrorProperties":{
        
    },
    "calculationProperties":{
        
    },
    "relations":{
        "target":{
            "title":"Target",
            "target":"snykTarget",
            "required":false,
            "many":false
        }
    }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: projects
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          title: .attributes.name
          blueprint: '"snykProject"'
          properties:
            type: .attributes.type
            targetFile: .attributes.target_file
            targetReference: .attributes.target_reference
            origin: .attributes.origin
            status: .attributes.status
            createdAt: .attributes.created
            tags: .attributes.tags
            businessCriticality: .attributes.business_criticality
            environment: .attributes.environment
          relations:
            target: .relationships.target.data.id

```
</details>

### Vulnerabilities
This kind represents a Snyk vulnerability.

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier":"snykVulnerability",
    "description":"This blueprint represents a Snyk vulnerability in our software catalog",
    "title":"Snyk Vulnerability",
    "icon":"Snyk",
    "schema":{
        "properties":{
            "priorityScore":{
            "type":"number",
            "title":"Priority Score"
            },
            "pkgName":{
            "type":"string",
            "title":"Package Name"
            },
            "pkgVersions":{
            "title":"Package Versions",
            "type":"array"
            },
            "issueType":{
            "type":"string",
            "title":"Issue Type",
            "enum": ["vuln", "license", "configuration"]
            },
            "issueSeverity":{
            "type":"string",
            "title":"Issue Severity",
            "enum": ["low", "medium", "high", "critical"],
            "enumColors": {
                "low": "green",
                "medium": "yellow",
                "high": "red",
                "critical": "red"
            }
            },
            "issueURL":{
            "type":"string",
            "format":"url",
            "title":"Issue URL"
            },
            "language":{
            "type":"string",
            "title":"Language"
            },
            "publicationTime":{
            "type":"string",
            "format":"date-time",
            "title":"Publication Time"
            },
            "isPatched":{
            "type":"string",
            "title":"Is Patched"
            }
        },
        "required":[
            
        ]
    },
    "mirrorProperties":{
        
    },
    "calculationProperties":{
        
    },
    "relations":{
        
    }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: vulnerabilities
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .issueData.id
          title: .issueData.title
          blueprint: '"snykVulnerability"'
          properties:
            priorityScore: .priorityScore
            pkgName: .pkgName
            pkgVersions: .pkgVersions
            issueType: .issueType
            issueSeverity: .issueData.severity
            issueURL: .issueData.url
            language: .issueData.language
            publicationTime: .issueData.publicationTime
            isPatched: .isPatched | tostring

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
├─ snyk_integration/             # The integration logic
│  ├─ client.py      # Wrapper to the Snyk REST API and other custom integration logic
├─ main.py              # The main exports the custom Ocean logic to the ocean sail command
├─ pyproject.toml
└─ Dockerfile
```