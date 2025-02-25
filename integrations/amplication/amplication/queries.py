# File for GraphQL queries
TEMPLATE_QUERY = """
query searchCatalog($where: ResourceWhereInputWithPropertiesFilter, $take: Int, $skip: Int) {
    catalog(where: $where, take: $take, skip: $skip) {
        totalCount
        data {
            id
            name
            description
            resourceType
            project {
                id
                name
            }
            blueprint {
                id
                name
            }
        }
        __typename
    }
}
"""

RESOURCE_QUERY = """
query searchCatalog($where: ResourceWhereInputWithPropertiesFilter, $take: Int, $skip: Int) {
    catalog(where: $where, take: $take, skip: $skip) {
        totalCount
        data {
            id
            name
            description
            resourceType
            project {
                id
                name
            }
            blueprint {
                id
                name
            }
            serviceTemplate {
                id
                name
                projectId
            }
            gitRepository {
                name
                gitOrganization {
                    name
                    provider
                }
            }
        }
        __typename
    }
}
"""

ALERTS_QUERY = """
fragment OutdatedVersionAlertFields on OutdatedVersionAlert {
    id
    createdAt
    updatedAt
    resourceId
    blockId
    block {
        id
        displayName
    }
    type
    outdatedVersion
    latestVersion
    status
}
query getOutdatedVersionAlerts(
    $where: OutdatedVersionAlertWhereInput
    $orderBy: OutdatedVersionAlertOrderByInput
    $take: Int
    $skip: Int
) {
    outdatedVersionAlerts(
        where: $where
        orderBy: $orderBy
        take: $take
        skip: $skip
    ) {
        ...OutdatedVersionAlertFields
    }
    _outdatedVersionAlertsMeta(where: $where) {
        count
    }
}
"""
