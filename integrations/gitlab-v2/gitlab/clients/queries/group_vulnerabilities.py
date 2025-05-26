VULNERABILITIES_QUERY = """
query($groupPath: ID!, $first: Int, $after: String, $severity: [VulnerabilitySeverity!]) {
  group(fullPath: $groupPath) {
    vulnerabilities(first: $first, after: $after, severity: $severity) {
      nodes {
        id
        uuid
        title
        description
        severity
        state
        reportType
        detectedAt
        confirmedAt
        dismissedAt
        resolvedAt
        updatedAt
        falsePositive
        presentOnDefaultBranch
        resolvedOnDefaultBranch
        hasRemediations
        dismissalReason
        solution
        vulnerabilityPath
        webUrl
        
        # Project information
        project {
          id
          name
          fullPath
          webUrl
        }
        
        # Primary identifier
        primaryIdentifier {
          name
          url
          externalType
          externalId
        }
        
        # Scanner information
        scanner {
          id
          name
          vendor
        }
        
        # Basic location (file and line info)
        location {
          ... on VulnerabilityLocationSast {
            file
            startLine
            endLine
          }
          ... on VulnerabilityLocationDependencyScanning {
            file
          }
          ... on VulnerabilityLocationSecretDetection {
            file
            startLine
            endLine
          }
        }
        
        # CVSS information
        cvss {
            vector
            version
            baseScore
            overallScore
            severity
            vendor
        }
      }
      pageInfo {
        endCursor
        hasNextPage
      }
    }
  }
}
"""
