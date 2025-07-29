#!/usr/bin/env python3
"""
Authentication Configuration Helper

This module handles all authentication setup for MCP servers,
keeping business logic clean and separated from auth concerns.
"""

import logging
import sys
from typing import TYPE_CHECKING

from pydantic import AnyHttpUrl
from mcp.server.auth.settings import AuthSettings

if TYPE_CHECKING:
    from mcp.server.fastmcp.server import FastMCP

# Import the token verifier
try:
    from token_verifier import IntrospectionTokenVerifier
except ImportError:
    print("Error: token_verifier.py not found in the current directory")
    print("Make sure token_verifier.py is in the same folder as this script")
    sys.exit(1)

logger = logging.getLogger(__name__)


def setup_auth_for_server(
    app: "FastMCP",
    auth_server_url: str = "http://localhost:9000",
    resource_server_url: str = "http://localhost:8001",
    oauth_strict: bool = False,
    required_scopes: list[str] = None
) -> None:
    """
    Configure authentication for an MCP server.
    
    This function separates all authentication concerns from business logic.
    
    Args:
        app: FastMCP server instance to configure
        auth_server_url: URL of the authorization server
        resource_server_url: URL of this resource server
        oauth_strict: Enable RFC 8707 resource validation
        required_scopes: List of required OAuth scopes (defaults to ["user"])
    """
    if required_scopes is None:
        required_scopes = ["user"]
    
    logger.info("🔧 Configuring authentication for MCP server...")
    
    try:
        # Parse URLs
        auth_server_parsed = AnyHttpUrl(auth_server_url)
        resource_server_parsed = AnyHttpUrl(resource_server_url)
        
        # Create introspection endpoint URL
        introspection_endpoint = f"{auth_server_url.rstrip('/')}/introspect"
        
        logger.info(f"📡 Introspection endpoint: {introspection_endpoint}")
        logger.info(f"🎯 Resource server URL: {resource_server_url}")
        logger.info(f"🔒 OAuth strict mode: {oauth_strict}")
        logger.info(f"🎫 Required scopes: {required_scopes}")
        
        # Create token verifier
        token_verifier = IntrospectionTokenVerifier(
            introspection_endpoint=introspection_endpoint,
            server_url=resource_server_url,
            validate_resource=oauth_strict,
        )
        
        # Create auth settings
        auth_settings = AuthSettings(
            issuer_url=auth_server_parsed,
            required_scopes=required_scopes,
            resource_server_url=resource_server_parsed,
        )
        
        # Apply authentication to the app
        app.token_verifier = token_verifier
        app.auth = auth_settings
        
        logger.info("✅ Authentication configured successfully")
        
    except ValueError as e:
        logger.error(f"❌ Invalid URL configuration: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to configure authentication: {e}")
        raise


def create_custom_token_verifier(
    introspection_endpoint: str,
    server_url: str,
    validate_resource: bool = False,
    timeout_seconds: float = 10.0
) -> IntrospectionTokenVerifier:
    """
    Create a custom token verifier with specific settings.
    
    Args:
        introspection_endpoint: OAuth introspection endpoint URL
        server_url: This server's URL for resource validation
        validate_resource: Enable RFC 8707 resource validation
        timeout_seconds: HTTP timeout for introspection requests
    
    Returns:
        Configured token verifier instance
    """
    logger.info(f"🔧 Creating custom token verifier...")
    logger.info(f"📡 Endpoint: {introspection_endpoint}")
    logger.info(f"⏱️ Timeout: {timeout_seconds}s")
    
    # Note: Current IntrospectionTokenVerifier doesn't support timeout parameter
    # This is a placeholder for future enhancement
    return IntrospectionTokenVerifier(
        introspection_endpoint=introspection_endpoint,
        server_url=server_url,
        validate_resource=validate_resource,
    )


def setup_auth_with_custom_verifier(
    app: "FastMCP",
    token_verifier: IntrospectionTokenVerifier,
    auth_server_url: str = "http://localhost:9000",
    resource_server_url: str = "http://localhost:8001",
    required_scopes: list[str] = None
) -> None:
    """
    Configure authentication with a custom token verifier.
    
    Args:
        app: FastMCP server instance to configure
        token_verifier: Custom token verifier instance
        auth_server_url: URL of the authorization server
        resource_server_url: URL of this resource server
        required_scopes: List of required OAuth scopes
    """
    if required_scopes is None:
        required_scopes = ["user"]
    
    logger.info("🔧 Configuring authentication with custom verifier...")
    
    try:
        # Parse URLs
        auth_server_parsed = AnyHttpUrl(auth_server_url)
        resource_server_parsed = AnyHttpUrl(resource_server_url)
        
        # Create auth settings
        auth_settings = AuthSettings(
            issuer_url=auth_server_parsed,
            required_scopes=required_scopes,
            resource_server_url=resource_server_parsed,
        )
        
        # Apply to app
        app.token_verifier = token_verifier
        app.auth = auth_settings
        
        logger.info("✅ Authentication with custom verifier configured successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to configure custom authentication: {e}")
        raise


# Convenience functions for common auth patterns
def setup_simple_auth(app: "FastMCP") -> None:
    """Set up simple authentication with default settings."""
    setup_auth_for_server(app)


def setup_strict_auth(app: "FastMCP") -> None:
    """Set up strict authentication with RFC 8707 resource validation."""
    setup_auth_for_server(app, oauth_strict=True)


def setup_multi_scope_auth(app: "FastMCP", scopes: list[str]) -> None:
    """Set up authentication with multiple required scopes."""
    setup_auth_for_server(app, required_scopes=scopes)


def _add_discovery_endpoints(app: "FastMCP", resource_server_url: str) -> None:
    """Add OAuth discovery endpoints to the FastMCP server."""
    import datetime
    
    logger.info("🔍 Adding OAuth discovery endpoints...")
    
    try:
        # Add protected resource metadata endpoint
        @app.get("/.well-known/oauth-protected-resource")
        async def oauth_protected_resource_metadata():
            """OAuth 2.0 Protected Resource Metadata (RFC 8705)."""
            return {
                "resource": resource_server_url,
                "authorization_servers": ["http://localhost:9000"],
                "scopes_supported": ["user"],
                "bearer_methods_supported": ["header"],
                "resource_documentation": f"{resource_server_url}/docs",
                "introspection_endpoint": "http://localhost:9000/introspect"
            }

        # Add health check endpoint
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "service": "oauth-protected-resource-server",
                "timestamp": datetime.datetime.now().isoformat()
            }
            
        logger.info("✅ OAuth discovery endpoints added")
        
    except Exception as e:
        logger.warning(f"⚠️ Could not add discovery endpoints: {e}")
        logger.info("💡 Discovery endpoints are optional - server will work without them")