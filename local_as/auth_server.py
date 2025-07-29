#!/usr/bin/env python3
"""
Standalone Authorization Server for MCP Split Demo.

Run with: python authz.py

This server handles OAuth flows, client registration, and token issuance.
Can be replaced with enterprise authorization servers like Auth0, Entra ID, etc.

NOTE: this is a simplified example for demonstration purposes.
This is not a production-ready implementation.
"""

import asyncio
import logging
import sys
import time

from pydantic import AnyHttpUrl, BaseModel
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from uvicorn import Config, Server

from mcp.server.auth.routes import cors_middleware, create_auth_routes
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions

# Import the simple auth provider (direct import - no relative import)
try:
    from simple_auth_provider import SimpleAuthSettings, SimpleOAuthProvider
except ImportError:
    print("Error: simple_auth_provider.py not found in the current directory")
    print("Make sure simple_auth_provider.py is in the same folder as this script")
    sys.exit(1)

logger = logging.getLogger(__name__)


class AuthServerSettings(BaseModel):
    """Settings for the Authorization Server."""

    # Server settings
    host: str = "localhost"
    port: int = 9000
    server_url: AnyHttpUrl = AnyHttpUrl("http://localhost:9000")
    auth_callback_path: str = "http://localhost:9000/login/callback"


class SimpleAuthProvider(SimpleOAuthProvider):
    """
    Authorization Server provider with simple demo authentication.

    This provider:
    1. Issues MCP tokens after simple credential authentication
    2. Stores token state for introspection by Resource Servers
    """

    def __init__(self, auth_settings: SimpleAuthSettings, auth_callback_path: str, server_url: str):
        super().__init__(auth_settings, auth_callback_path, server_url)


def create_authorization_server(server_settings: AuthServerSettings, auth_settings: SimpleAuthSettings) -> Starlette:
    """Create the Authorization Server application."""
    oauth_provider = SimpleAuthProvider(
        auth_settings, server_settings.auth_callback_path, str(server_settings.server_url)
    )

    mcp_auth_settings = AuthSettings(
        issuer_url=server_settings.server_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[auth_settings.mcp_scope],
            default_scopes=[auth_settings.mcp_scope],
        ),
        required_scopes=[auth_settings.mcp_scope],
        resource_server_url=None,
    )

    # Create OAuth routes
    routes = create_auth_routes(
        provider=oauth_provider,
        issuer_url=mcp_auth_settings.issuer_url,
        service_documentation_url=mcp_auth_settings.service_documentation_url,
        client_registration_options=mcp_auth_settings.client_registration_options,
        revocation_options=mcp_auth_settings.revocation_options,
    )

    # Add login page route (GET)
    async def login_page_handler(request: Request) -> Response:
        """Show login form."""
        state = request.query_params.get("state")
        if not state:
            raise HTTPException(400, "Missing state parameter")
        return await oauth_provider.get_login_page(state)

    routes.append(Route("/login", endpoint=login_page_handler, methods=["GET"]))

    # Add login callback route (POST)
    async def login_callback_handler(request: Request) -> Response:
        """Handle simple authentication callback."""
        return await oauth_provider.handle_login_callback(request)

    routes.append(Route("/login/callback", endpoint=login_callback_handler, methods=["POST"]))

    # Add token introspection endpoint (RFC 7662) for Resource Servers
    async def introspect_handler(request: Request) -> Response:
        """
        Token introspection endpoint for Resource Servers.

        Resource Servers call this endpoint to validate tokens without
        needing direct access to token storage.
        """
        form = await request.form()
        token = form.get("token")
        if not token or not isinstance(token, str):
            return JSONResponse({"active": False}, status_code=400)

        # Look up token in provider
        access_token = await oauth_provider.load_access_token(token)
        if not access_token:
            return JSONResponse({"active": False})

        return JSONResponse(
            {
                "active": True,
                "client_id": access_token.client_id,
                "scope": " ".join(access_token.scopes),
                "exp": access_token.expires_at,
                "iat": int(time.time()),
                "token_type": "Bearer",
                "aud": access_token.resource,  # RFC 8707 audience claim
            }
        )

    routes.append(
        Route(
            "/introspect",
            endpoint=cors_middleware(introspect_handler, ["POST", "OPTIONS"]),
            methods=["POST", "OPTIONS"],
        )
    )

    # Add OAuth discovery endpoints (RFC 8414)
    async def oauth_authorization_server_handler(request: Request) -> Response:
        """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
        metadata = {
            "issuer": str(server_settings.server_url),
            "authorization_endpoint": f"{server_settings.server_url}/oauth/authorize",
            "token_endpoint": f"{server_settings.server_url}/oauth/token",
            "introspection_endpoint": f"{server_settings.server_url}/introspect",
            "registration_endpoint": f"{server_settings.server_url}/oauth/register",
            "revocation_endpoint": f"{server_settings.server_url}/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
            "scopes_supported": [auth_settings.mcp_scope],
            "code_challenge_methods_supported": ["S256"],
            "introspection_endpoint_auth_methods_supported": ["client_secret_post"],
            "revocation_endpoint_auth_methods_supported": ["client_secret_post"]
        }
        return JSONResponse(metadata)

    routes.append(
        Route(
            "/.well-known/oauth-authorization-server",
            endpoint=cors_middleware(oauth_authorization_server_handler, ["GET", "OPTIONS"]),
            methods=["GET", "OPTIONS"]
        )
    )

    # Add health check endpoint
    async def health_handler(request: Request) -> Response:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy", "service": "authorization-server"})

    routes.append(Route("/health", endpoint=health_handler, methods=["GET"]))

    # Add health check endpoint
    async def health_handler(request: Request) -> Response:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy", "service": "authorization-server"})

    routes.append(Route("/health", endpoint=health_handler, methods=["GET"]))

    # Add OAuth discovery endpoints (RFC 8414)
    async def oauth_authorization_server_handler(request: Request) -> Response:
        """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
        metadata = {
            "issuer": str(server_settings.server_url),
            "authorization_endpoint": f"{server_settings.server_url}/oauth/authorize",
            "token_endpoint": f"{server_settings.server_url}/oauth/token",
            "introspection_endpoint": f"{server_settings.server_url}/introspect",
            "registration_endpoint": f"{server_settings.server_url}/oauth/register",
            "revocation_endpoint": f"{server_settings.server_url}/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
            "scopes_supported": [auth_settings.mcp_scope],
            "code_challenge_methods_supported": ["S256"],
            "introspection_endpoint_auth_methods_supported": ["client_secret_post"],
            "revocation_endpoint_auth_methods_supported": ["client_secret_post"]
        }
        return JSONResponse(metadata)

    routes.append(
        Route(
            "/.well-known/oauth-authorization-server",
            endpoint=cors_middleware(oauth_authorization_server_handler, ["GET", "OPTIONS"]),
            methods=["GET", "OPTIONS"]
        )
    )

    return Starlette(routes=routes)


async def run_server(server_settings: AuthServerSettings, auth_settings: SimpleAuthSettings):
    """Run the Authorization Server."""
    auth_server = create_authorization_server(server_settings, auth_settings)

    config = Config(
        auth_server,
        host=server_settings.host,
        port=server_settings.port,
        log_level="info",
    )
    server = Server(config)

    logger.info(f"🚀 MCP Authorization Server running on {server_settings.server_url}")
    logger.info(f"🔑 Demo credentials: demo_user / demo_password")
    logger.info(f"🌐 Login page: {server_settings.server_url}/login")
    logger.info(f"🔍 Health check: {server_settings.server_url}/health")
    logger.info("💡 Start Resource Server next: python mcp_server.py")

    await server.serve()


def main():
    """Main entry point for the Authorization Server."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="MCP Authorization Server")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    
    args = parser.parse_args()

    try:
        # Load simple auth settings
        auth_settings = SimpleAuthSettings()

        # Create server settings
        server_url = f"http://{args.host}:{args.port}"
        server_settings = AuthServerSettings(
            host=args.host,
            port=args.port,
            server_url=AnyHttpUrl(server_url),
            auth_callback_path=f"{server_url}/login",
        )

        logger.info(f"🔧 Starting Authorization Server on {server_url}")
        logger.info(f"👤 Demo user: {auth_settings.demo_username}")
        logger.info(f"🔐 Demo password: {auth_settings.demo_password}")

        # Run the server
        asyncio.run(run_server(server_settings, auth_settings))
        return 0
    except KeyboardInterrupt:
        logger.info("Authorization Server stopped by user")
        return 0
    except Exception as e:
        logger.exception(f"Authorization Server error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())