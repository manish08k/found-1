"""
Integration SDK — Public API.

Import everything needed to build a new integration from this package::

    from integrations.sdk import (
        BaseIntegration,
        CredentialField,
        operation,
        trigger,
        ResilientHTTPClient,
        CursorPaginator,
        OffsetPaginator,
        LinkHeaderPaginator,
        PageNumberPaginator,
        ApiKeyAuth,
        BearerAuth,
        BasicAuth,
        OAuthTokenAuth,
        QueryParamAuth,
        IntegrationError,
        AuthenticationError,
        RateLimitError,
        NotFoundError,
        ValidationError,
        ServerError,
        CredentialHelper,
        IntegrationRegistry,
        INTEGRATION_REGISTRY,
        IntegrationGenerator,
        IntegrationTestCase,
        MockHTTPClient,
        MockDB,
        fixture_response,
    )
"""

# Base class & credential field descriptor
from integrations.sdk.base import BaseIntegration, CredentialField

# Decorators
from integrations.sdk.decorators import operation, trigger, OperationMeta, TriggerMeta

# HTTP client
from integrations.sdk.http import ResilientHTTPClient

# Pagination helpers
from integrations.sdk.pagination import (
    CursorPaginator,
    OffsetPaginator,
    LinkHeaderPaginator,
    PageNumberPaginator,
)

# Auth helpers
from integrations.sdk.auth import (
    ApiKeyAuth,
    BearerAuth,
    BasicAuth,
    OAuthTokenAuth,
    QueryParamAuth,
)

# Error types
from integrations.sdk.errors import (
    IntegrationError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    ValidationError,
    ServerError,
)

# Credential helper
from integrations.sdk.credential_helper import CredentialHelper

# Registry
from integrations.sdk.registry import IntegrationRegistry, INTEGRATION_REGISTRY

# Code generator
from integrations.sdk.generator import IntegrationGenerator

# Test helpers
from integrations.sdk.testing import (
    IntegrationTestCase,
    MockHTTPClient,
    MockDB,
    fixture_response,
    MockResponse,
    RecordedRequest,
)

__all__ = [
    # Base
    "BaseIntegration",
    "CredentialField",
    # Decorators
    "operation",
    "trigger",
    "OperationMeta",
    "TriggerMeta",
    # HTTP
    "ResilientHTTPClient",
    # Pagination
    "CursorPaginator",
    "OffsetPaginator",
    "LinkHeaderPaginator",
    "PageNumberPaginator",
    # Auth
    "ApiKeyAuth",
    "BearerAuth",
    "BasicAuth",
    "OAuthTokenAuth",
    "QueryParamAuth",
    # Errors
    "IntegrationError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
    "ServerError",
    # Credentials
    "CredentialHelper",
    # Registry
    "IntegrationRegistry",
    "INTEGRATION_REGISTRY",
    # Generator
    "IntegrationGenerator",
    # Testing
    "IntegrationTestCase",
    "MockHTTPClient",
    "MockDB",
    "MockResponse",
    "RecordedRequest",
    "fixture_response",
]
