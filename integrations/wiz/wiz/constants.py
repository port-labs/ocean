PAGE_SIZE = 100
AUTH0_URLS = ["https://auth.wiz.io/oauth/token", "https://auth0.gov.wiz.io/oauth/token"]
COGNITO_URLS = [
    "https://auth.app.wiz.io/oauth/token",
    "https://auth.gov.wiz.io/oauth/token",
]

ISSUES_GQL = """
query IssuesTable(
  $filterBy: IssueFilters
  $first: Int
  $after: String
  $orderBy: IssueOrder
) {
  issues: issuesV2(
    filterBy: $filterBy
    first: $first
    after: $after
    orderBy: $orderBy
  ) {
    nodes {
      id
      sourceRule {
        __typename
        ... on Control {
          id
          name
          controlDescription: description
          resolutionRecommendation
          securitySubCategories {
            title
            category {
              name
              framework {
                name
              }
            }
          }
        }
        ... on CloudEventRule {
          id
          name
          cloudEventRuleDescription: description
          sourceType
          type
        }
        ... on CloudConfigurationRule {
          id
          name
          cloudConfigurationRuleDescription: description
          remediationInstructions
          serviceType
        }
      }
      createdAt
      updatedAt
      dueAt
      type
      resolvedAt
      statusChangedAt
      projects {
        id
        name
        slug
        businessUnit
        riskProfile {
          businessImpact
        }
      }
      status
      severity
      entitySnapshot {
        id
        type
        nativeType
        name
        status
        cloudPlatform
        cloudProviderURL
        providerId
        region
        resourceGroupExternalId
        subscriptionExternalId
        subscriptionName
        subscriptionTags
        tags
        createdAt
        externalId
      }
      serviceTickets {
        externalId
        name
        url
      }
      notes {
        createdAt
        updatedAt
        text
        user {
          name
          email
        }
        serviceAccount {
          name
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""
PROJECTS_GQL = """
query ProjectsTable(
  $filterBy: ProjectFilters,
  $first: Int,
  $after: String,
  $orderBy: ProjectOrder
) {
  projects(
    filterBy: $filterBy,
    first: $first,
    after: $after,
    orderBy: $orderBy
  ) {
    nodes {
      id
      name
      isFolder
      archived
      businessUnit
      description
    }
  }
}
"""
VULNERABILITY_FINDINGS_GQL = """
query VulnerabilityFindingsTable(
  $filterBy: VulnerabilityFindingFilters
  $first: Int
  $after: String
  $orderBy: VulnerabilityFindingOrder
) {
  vulnerabilityFindings(
    filterBy: $filterBy
    first: $first
    after: $after
    orderBy: $orderBy
  ) {
    nodes {
      id
      severity
      categories
      version
      detectionMethod
      score
      status
      description
      resolvedAt
      updatedAt
      firstDetectedAt
      publishedDate
      remediation
      environments
      link
      vulnerabilityExternalId
      portalUrl
      origin
      CVEDescription
      name
      detailedName
      artifactType {
        group
        ciComponent
        custom
        plugin
        osPackageManager
        codeLibraryLanguage
      }
      hasFix
      hasExploit
      isHighProfileThreat
      projects {
        id
        name
      }
      rootComponent {
        name
      }
      applicationServices {
        id
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

TECHNOLOGIES_GQL = """
query TechnologiesTable(
  $filterBy: TechnologyFilters
  $first: Int
  $after: String
  $orderBy: TechnologyOrder
) {
  technologies(
    filterBy: $filterBy
    first: $first
    after: $after
    orderBy: $orderBy
  ) {
    nodes {
      id
      name
      description
      categories {
        name
      }
      usage
      status
      risk
      note
      ownerName
      businessModel
      popularity
      projectCount
      codeRepoCount
      isCloudService
      supportedOperatingSystems
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

HOSTED_TECHNOLOGIES_GQL = """
query HostedTechnologiesTable(
  $filterBy: HostedTechnologyFilters
  $first: Int
  $after: String
  $orderBy: HostedTechnologyOrder
) {
  hostedTechnologies(
    filterBy: $filterBy
    first: $first
    after: $after
    orderBy: $orderBy
  ) {
    nodes {
      id
      name
      technology {
        id
        name
      }
      resource {
        id
        name
      }
      detectionMethods
      installedPackages
      firstSeen
      updatedAt
      cpe
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

REPOSITORIES_GQL = """
query RepositoriesTable(
  $filterBy: RepositoryFilters
  $first: Int
  $after: String
) {
  repositories(
    filterBy: $filterBy
    first: $first
    after: $after
  ) {
    nodes {
      id
      name
      url
      platform
      public
      archived
      visibility
      organization {
        id
        name
      }
      branches {
        id
        name
        url
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

GRAPH_QUERIES = {
    "issues": ISSUES_GQL,
    "projects": PROJECTS_GQL,
    "vulnerabilityFindings": VULNERABILITY_FINDINGS_GQL,
    "technologies": TECHNOLOGIES_GQL,
    "hostedTechnologies": HOSTED_TECHNOLOGIES_GQL,
    "repositories": REPOSITORIES_GQL,
}
