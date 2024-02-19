PAGE_SIZE = 50
MAX_PAGES = 5
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
CREATE_REPORT_MUTATION = """
    mutation CreateReport($input: CreateReportInput!) {
      createReport(input: $input) {
        report {
          id
        }
      }
    }
    """
# The GraphQL mutation that rerun report and return report ID
RERUN_REPORT_MUTATION = """
    mutation RerunReport($reportId: ID!) {
        rerunReport(input: { id: $reportId }) {
            report {
                id
            }
        }
    }
"""

GRAPH_QUERIES = {
    "issues": ISSUES_GQL,
    "projects": PROJECTS_GQL,
    "create_report": CREATE_REPORT_MUTATION,
}

GET_REPORT = """
query ReportsTable($filterBy: ReportFilters, $first: Int, $after: String) {
  reports(first: $first, after: $after, filterBy: $filterBy) {
    nodes {
      id
      name
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

DOWNLOAD_REPORT_QUERY = """
    query ReportDownloadUrl($reportId: ID!) {
        report(id: $reportId) {
            lastRun {
                url
                status
            }
        }
    }
"""

RERUN_REPORT_MUTATION = """
    mutation RerunReport($reportId: ID!) {
        rerunReport(input: { id: $reportId }) {
            report {
                id
            }
        }
    }
"""

# Configuration variables
MAX_RETRIES_FOR_QUERY = 5
RETRY_TIME_FOR_QUERY = 2
MAX_RETRIES_FOR_DOWNLOAD_REPORT = 5
RETRY_TIME_FOR_DOWNLOAD_REPORT = 60
CHECK_INTERVAL_FOR_DOWNLOAD_REPORT = 20

PORT_REPORT_NAME = "port-integration-report"
