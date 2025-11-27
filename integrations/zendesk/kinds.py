"""
Kind definitions for Zendesk domain objects

Based on requirements to support: ticket, side_conversation, user, organization
Following Ocean integration patterns for resource kind definitions.

Purpose: Define the resource types that this integration will sync
Expected output: String constants for each supported resource kind
"""


class Kinds:
    """
    Resource kind constants for Zendesk integration
    
    Supports the four main domain objects as specified:
    - ticket: Customer support tickets
    - side_conversation: Side conversations within tickets
    - user: Users (end-users, agents, admins)
    - organization: Organizations/companies
    """
    
    TICKET = "ticket"
    SIDE_CONVERSATION = "side_conversation" 
    USER = "user"
    ORGANIZATION = "organization"