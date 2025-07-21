from typing import Optional, Union, List
from botocore.utils import ArnParser


class AWSSessionError(Exception):
    """Raised when an AWS session or assume role operation fails."""


class CredentialsProviderError(Exception):
    """Raised when there is a credentials provider or assume role error."""


def normalize_arn_list(arn_input: Optional[Union[str, List[str]]]) -> List[str]:
    """Return a list of non-empty ARN strings from input (str, list, or None)."""
    if not arn_input:
        return []
    if isinstance(arn_input, str):
        arn_input = [arn_input]
    return [arn.strip() for arn in arn_input if isinstance(arn, str) and arn.strip()]


def extract_account_from_arn(arn: str, arn_parser: ArnParser = ArnParser()) -> str:
    """Extract account ID from ARN. Raises if parsing fails."""
    arn_data = arn_parser.parse_arn(arn)
    return arn_data["account"]
