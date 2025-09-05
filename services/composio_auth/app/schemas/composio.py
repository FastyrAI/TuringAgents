"""
Pydantic schemas for the Composio module.
Handles tool discovery, natural language processing, and tool execution.
Now with smart Redis caching for improved performance and automatic refresh.
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from clients.composio_client import ComposioClient

logger = logging.getLogger(__name__)


class ToolInfo(BaseModel):
    """Information about an available tool."""

    id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool description")
    connected: bool = Field(..., description="Whether user has connected this tool")
    auth_url: Optional[str] = Field(None, description="OAuth URL if not connected")


class ToolDiscoveryResponse(BaseModel):
    """Response for tool discovery endpoint."""

    tools: List[ToolInfo] = Field(..., description="List of available tools")


class NaturalLanguageRequest(BaseModel):
    """Request for natural language processing."""

    query: str = Field(..., description="Natural language query from user")


class ToolExecutionRequest(BaseModel):
    """Request for tool execution."""

    tool_id: str = Field(..., description="ID of the tool to execute")
    parameters: Dict[str, Any] = Field(..., description="Tool-specific parameters")


class ToolExecutionResponse(BaseModel):
    """Response for tool execution."""

    success: bool = Field(..., description="Whether execution was successful")
    message: str = Field(..., description="Result message")
    data: Optional[Dict[str, Any]] = Field(
        None, description="Tool-specific response data"
    )


class AccountConnectionRequest(BaseModel):
    """Request to connect an account for a specific tool."""

    tool_id: str = Field(..., description="ID of the tool to connect")


class AccountConnectionResponse(BaseModel):
    """Response for account connection."""

    auth_url: str = Field(..., description="OAuth URL for account connection")
    message: str = Field(..., description="Connection instructions")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class AuthUrlResponse(BaseModel):
    """Response model for OAuth initiation."""

    auth_url: str = Field(
        ..., description="URL to redirect user for OAuth authorization"
    )


class ProviderInfo(BaseModel):
    """Information about a provider"""

    name: str = Field(..., description="Provider identifier (e.g., 'gmail')")
    display_name: str = Field(..., description="Human-readable provider name")
    description: str = Field(..., description="Provider description")
    connected: bool = Field(..., description="Whether user has connected this provider")
    connection_count: int = Field(
        default=0, description="Number of connections for this provider"
    )
    last_connected: Optional[str] = Field(None, description="Last connection timestamp")
    status: str = Field(
        default="available", description="Provider status: available, connected, error"
    )
    auth_type: str = Field(..., description="Authentication type: 'oauth' or 'api_key'")
    requires_redirect: bool = Field(
        ..., description="Whether this auth type requires browser redirect"
    )


class ProvidersListResponse(BaseModel):
    """Response for available providers list"""

    providers: List[ProviderInfo] = Field(
        ..., description="List of available providers"
    )
    total: int = Field(..., description="Total number of providers")


class ComposioConnectionBase(BaseModel):
    provider: str
    created_at: datetime


class ComposioConnection(ComposioConnectionBase):
    id: int
    user_id: int
    composio_connected_account_id: str
    updated_at: datetime

    class Config:
        from_attributes = True


class ComposioConnectionList(BaseModel):
    connections: List[ComposioConnection]
    total: int


class ApiKeyConnectionRequest(BaseModel):
    """Request to connect using API key authentication."""

    provider: str = Field(
        ..., description="Provider identifier (e.g., 'exa', 'firecrawl')"
    )
    api_key: str = Field(..., description="API key for the provider")


class ApiKeyConnectionResponse(BaseModel):
    """Response for API key connection."""

    success: bool = Field(..., description="Whether connection was successful")
    message: str = Field(..., description="Connection result message")
    connection_id: Optional[str] = Field(
        None, description="Composio connection ID if successful"
    )


class ProviderAuthTypeResponse(BaseModel):
    """Response for provider authentication type."""

    provider: str = Field(..., description="Provider identifier")
    auth_type: str = Field(..., description="Authentication type: 'oauth' or 'api_key'")
    requires_redirect: bool = Field(
        ..., description="Whether this auth type requires browser redirect"
    )


class AuthTypeEnum(str, Enum):
    oauth2 = "oauth2"
    api_key = "api_key"


def create_provider_enum():
    """Create ProviderEnum dynamically from available providers."""
    client = ComposioClient()
    try:
        providers = client.get_composio_providers()
        enum_dict = {}
        for provider in providers:
            enum_name = provider.upper().replace("-", "_").replace(" ", "_")
            enum_dict[enum_name] = provider

        # Create the enum class
        DynamicProviderEnum = Enum("ProviderEnum", enum_dict)
        logger.info(f"Created ProviderEnum with {len(enum_dict)} providers")
        return DynamicProviderEnum

    except Exception as e:
        logger.error(f"Failed to create ProviderEnum: {e}")
        # Emergency fallback
        return Enum(
            "ProviderEnum",
            {
                "GMAIL": "gmail",
                "GOOGLECALENDAR": "googlecalendar",
            },
        )


# Create the enum at module level
ProviderEnum = create_provider_enum()
