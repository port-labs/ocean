"""
Custom exceptions for HTTP Server integration authentication.

These exceptions provide more specific error types than generic ValueError,
making error handling and debugging easier.
"""


class CustomAuthError(Exception):
    """Base exception for all custom authentication errors"""

    pass


class CustomAuthConfigError(CustomAuthError):
    """Raised when there's a configuration error in custom auth setup"""

    pass


class TemplateSyntaxError(CustomAuthError):
    """Raised when template syntax is invalid (e.g., missing dot in {{.path}})"""

    pass


class TemplateEvaluationError(CustomAuthError):
    """Raised when template evaluation fails for any reason"""

    pass


class TemplateVariableNotFoundError(TemplateEvaluationError):
    """Raised when a template variable is not found in the auth response"""

    pass


class AuthResponseHashGenerationError(CustomAuthError):
    """Raised when failed to generate hash for auth response"""

    pass


class CustomAuthRequestError(CustomAuthError):
    """Raised when custom auth request configuration is invalid or missing"""

    pass


class CustomAuthResponseError(CustomAuthError):
    """Raised when custom auth response configuration is invalid or missing"""

    pass
