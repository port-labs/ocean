RESOURCE_CONTAINERS_QUERY: str = """
        resourcecontainers
        {}
        | project id, type, name, location, tags, subscriptionId, resourceGroup
        | extend resourceGroup=tolower(resourceGroup)
        | extend type=tolower(type)
        """

RESOURCES_QUERY = """
    resources
    | project id, type, name, location, tags, subscriptionId, resourceGroup
    | extend resourceGroup=tolower(resourceGroup)
    | extend type=tolower(type)
    {}
    | join kind=leftouter (
        resourcecontainers
        | where type =~ 'microsoft.resources/subscriptions/resourcegroups'
        | project rgName=tolower(name), rgTags=tags, rgSubscriptionId=subscriptionId
    ) on $left.subscriptionId == $right.rgSubscriptionId and $left.resourceGroup == $right.rgName
    {}
    | project id, type, name, location, tags, subscriptionId, resourceGroup, rgTags
    """
