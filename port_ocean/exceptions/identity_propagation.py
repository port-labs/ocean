from port_ocean.exceptions.base import BaseOceanException


class IdentityPropagationError(BaseOceanException):
    """Base class for all identity propagation errors."""

    pass


class VaultError(IdentityPropagationError):
    """Vault unreachable or returned an unexpected error. A miss (secret not found) returns None, not this."""

    pass


class IdentityVerifierNotAvailableError(IdentityPropagationError):
    """No verifier is wired in yet. Fails closed - callers must reject, not fall through."""

    pass


class IdentityVerificationError(IdentityPropagationError):
    """Identity token is invalid, expired, or not for this target."""

    pass


class OAuthError(IdentityPropagationError):
    """Provider rejected an authorization code or refresh token."""

    pass


class UserAuthRequiredError(IdentityPropagationError):
    """User must (re-)authenticate. Not an ActionExecutionError — pauses the run, does not fail it."""

    pass


class OAuthProviderNotConfiguredError(IdentityPropagationError):
    """No OAuth provider has been registered for this integration process."""

    pass


class DuplicateOAuthProviderError(IdentityPropagationError):
    """Raised when register_oauth_provider is called more than once in the same process —
    each Ocean process hosts exactly one integration and so exactly one OAuth provider.
    """

    pass
