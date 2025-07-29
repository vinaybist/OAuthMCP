#!/usr/bin/env python3
"""
Simple MCP client example with LAZY OAuth authentication support.

This client connects to an MCP server but only authenticates when tools are actually used.
"""

import asyncio
import os
import threading
import time
import webbrowser
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken


class InMemoryTokenStorage(TokenStorage):
    """Simple in-memory token storage implementation."""

    def __init__(self):
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._client_info = client_info


class CallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to capture OAuth callback."""

    def __init__(self, request, client_address, server, callback_data):
        """Initialize with callback data storage."""
        self.callback_data = callback_data
        super().__init__(request, client_address, server)

    def do_GET(self):
        """Handle GET request from OAuth redirect."""
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        if "code" in query_params:
            self.callback_data["authorization_code"] = query_params["code"][0]
            self.callback_data["state"] = query_params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <script>setTimeout(() => window.close(), 2000);</script>
            </body>
            </html>
            """)
        elif "error" in query_params:
            self.callback_data["error"] = query_params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"""
            <html>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {query_params["error"][0]}</p>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """.encode()
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class CallbackServer:
    """Simple server to handle OAuth callbacks."""

    def __init__(self, port=3030):
        self.port = port
        self.server = None
        self.thread = None
        self.callback_data = {"authorization_code": None, "state": None, "error": None}

    def _create_handler_with_data(self):
        """Create a handler class with access to callback data."""
        callback_data = self.callback_data

        class DataCallbackHandler(CallbackHandler):
            def __init__(self, request, client_address, server):
                super().__init__(request, client_address, server, callback_data)

        return DataCallbackHandler

    def start(self):
        """Start the callback server in a background thread."""
        handler_class = self._create_handler_with_data()
        self.server = HTTPServer(("localhost", self.port), handler_class)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"🖥️  Started callback server on http://localhost:{self.port}")

    def stop(self):
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for_callback(self, timeout=300):
        """Wait for OAuth callback with timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.callback_data["authorization_code"]:
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                raise Exception(f"OAuth error: {self.callback_data['error']}")
            time.sleep(0.1)
        raise Exception("Timeout waiting for OAuth callback")

    def get_state(self):
        """Get the received state parameter."""
        return self.callback_data["state"]


class LazyAuthClient:
    """MCP client with lazy authentication - only authenticates when tools are used."""

    def __init__(self, server_url: str, transport_type: str = "streamable_http"):
        self.server_url = server_url
        self.transport_type = transport_type
        self.session: ClientSession | None = None
        self._authenticated = False
        self._connection_lock = asyncio.Lock()
        self._transport_context = None
        self._session_context = None

    async def connect(self):
        """Connect to the MCP server WITHOUT authentication."""
        print(f"🔗 Connecting to {self.server_url} (authentication will happen when needed)...")
        
        # Test basic connectivity first
        import httpx
        try:
            print(f"🔍 Testing basic connectivity to {self.server_url}...")
            async with httpx.AsyncClient() as client:
                response = await client.get(self.server_url.replace("/mcp", "/health"))
                print(f"✅ Health check response: {response.status_code}")
        except Exception as e:
            print(f"❌ Basic connectivity test failed: {e}")
            print(f"💡 Make sure your MCP server is running on port 8080")
            return

        print("✅ Basic connectivity established")
        print("🔒 Authentication will be triggered when you first use a tool")
        
        # Start interactive loop immediately without authentication
        await self.interactive_loop()

    async def _ensure_authenticated_session(self):
        """Ensure we have an authenticated session, creating one if needed."""
        async with self._connection_lock:
            if self.session and self._authenticated:
                return  # Already authenticated

            print("\n🔐 Authentication required - starting OAuth flow...")
            
            # Clean up any existing connection first
            await self._cleanup_connection()
            
            try:
                callback_server = CallbackServer(port=3030)
                callback_server.start()

                async def callback_handler() -> tuple[str, str | None]:
                    """Wait for OAuth callback and return auth code and state."""
                    print("⏳ Waiting for authorization callback...")
                    try:
                        auth_code = callback_server.wait_for_callback(timeout=300)
                        print(f"✅ Received authorization code: {auth_code[:10]}...")
                        return auth_code, callback_server.get_state()
                    except Exception as e:
                        print(f"❌ Callback handler error: {e}")
                        raise
                    finally:
                        print("🔄 Stopping callback server...")
                        callback_server.stop()

                client_metadata_dict = {
                    "client_name": "Lazy Auth Client",
                    "redirect_uris": ["http://localhost:3030/callback"],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "client_secret_post",
                }

                async def _default_redirect_handler(authorization_url: str) -> None:
                    """Default redirect handler that opens the URL in a browser."""
                    print(f"🌐 Opening browser for authorization: {authorization_url}")
                    webbrowser.open(authorization_url)

                print("🔧 Setting up OAuth provider...")
                # Create OAuth authentication handler using the new interface
                oauth_auth = OAuthClientProvider(
                    server_url=self.server_url.replace("/mcp", ""),
                    client_metadata=OAuthClientMetadata.model_validate(
                        client_metadata_dict
                    ),
                    storage=InMemoryTokenStorage(),
                    redirect_handler=_default_redirect_handler,
                    callback_handler=callback_handler,
                )

                print("🔧 Creating authenticated transport connection...")
                
                # Create transport with auth handler based on transport type
                if self.transport_type == "sse":
                    print("📡 Opening SSE transport connection with auth...")
                    self._transport_context = sse_client(
                        url=self.server_url,
                        auth=oauth_auth,
                        timeout=60,
                    )
                else:
                    print("📡 Opening StreamableHTTP transport connection with auth...")
                    self._transport_context = streamablehttp_client(
                        url=self.server_url,
                        auth=oauth_auth,
                        timeout=timedelta(seconds=60),
                    )

                print("🔗 Establishing connection...")
                # Enter the transport context
                if self.transport_type == "sse":
                    (read_stream, write_stream) = await self._transport_context.__aenter__()
                    get_session_id = None
                else:
                    (read_stream, write_stream, get_session_id) = await self._transport_context.__aenter__()

                print("✅ Transport connection established!")
                
                # Initialize the session with proper context manager
                await self._initialize_session(read_stream, write_stream, get_session_id)

            except Exception as e:
                print(f"❌ Failed to authenticate: {e}")
                import traceback
                traceback.print_exc()
                # Clean up if authentication failed
                await self._cleanup_connection()
                raise

    async def _cleanup_connection(self):
        """Clean up all connections."""
        # Clean up session first
        if self._session_context:
            try:
                print("🧹 Cleaning up session context...")
                await self._session_context.__aexit__(None, None, None)
            except Exception as e:
                print(f"Warning: Error during session cleanup: {e}")
            finally:
                self._session_context = None
                self.session = None

        # Then clean up transport
        if self._transport_context:
            try:
                print("🧹 Cleaning up transport connection...")
                await self._transport_context.__aexit__(None, None, None)
            except Exception as e:
                print(f"Warning: Error during transport cleanup: {e}")
            finally:
                self._transport_context = None

        self._authenticated = False

    async def _initialize_session(self, read_stream, write_stream, get_session_id):
        """Initialize the MCP session with the given streams using proper context manager."""
        print("🤝 Initializing MCP session...")
        
        try:
            # Create session context manager - this is the key fix!
            print("🔧 Creating ClientSession context manager...")
            self._session_context = ClientSession(read_stream, write_stream)
            
            print("⚡ Starting session initialization...")
            
            # Use the context manager properly
            self.session = await self._session_context.__aenter__()
            print("✅ Session context entered successfully")
            
            print("📤 About to send MCP initialize message...")
            
            # Add more granular timeout and debugging
            start_time = time.time()
            try:
                await asyncio.wait_for(self.session.initialize(), timeout=30.0)
                elapsed = time.time() - start_time
                print(f"✨ Session initialization complete! (took {elapsed:.2f}s)")
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                print(f"❌ Session initialization timed out after {elapsed:.2f}s")
                print("💡 The initialize() call never returned - likely a transport issue")
                raise

            print(f"\n✅ Authenticated and connected to MCP server at {self.server_url}")
            if get_session_id:
                session_id = get_session_id()
                if session_id:
                    print(f"Session ID: {session_id}")

            self._authenticated = True
            print("🎉 Ready to use tools!")
            
        except asyncio.TimeoutError:
            print("❌ Session initialization timed out after 30 seconds")
            print("💡 This usually means the MCP server isn't responding to initialization messages")
            print("🔍 Check if your server properly implements the MCP protocol initialization")
            print("🔍 Expected server logs: You should see POST requests to /mcp endpoint")
            raise
        except Exception as e:
            print(f"❌ Session initialization failed: {e}")
            print(f"📋 Error type: {type(e).__name__}")
            import traceback
            print("📋 Full traceback:")
            traceback.print_exc()
            raise

    async def cleanup(self):
        """Clean up resources."""
        await self._cleanup_connection()

    async def list_tools(self):
        """List available tools from the server - triggers auth if needed."""
        print("📋 Listing tools...")
        
        # This will trigger authentication if not already done
        await self._ensure_authenticated_session()
        
        if not self.session:
            print("❌ Failed to establish authenticated session")
            return

        try:
            result = await self.session.list_tools()
            if hasattr(result, "tools") and result.tools:
                print("\n📋 Available tools:")
                for i, tool in enumerate(result.tools, 1):
                    print(f"{i}. {tool.name}")
                    if tool.description:
                        print(f"   Description: {tool.description}")
                    print()
            else:
                print("No tools available")
        except Exception as e:
            print(f"❌ Failed to list tools: {e}")
            print("🔄 Resetting connection - try again...")
            # Reset authentication state so user can try again
            await self.cleanup()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None):
        """Call a specific tool - triggers auth if needed."""
        print(f"🔧 Calling tool '{tool_name}'...")
        
        # This will trigger authentication if not already done
        await self._ensure_authenticated_session()
        
        if not self.session:
            print("❌ Failed to establish authenticated session")
            return

        try:
            result = await self.session.call_tool(tool_name, arguments or {})
            print(f"\n🔧 Tool '{tool_name}' result:")
            if hasattr(result, "content"):
                for content in result.content:
                    if content.type == "text":
                        print(content.text)
                    else:
                        print(content)
            else:
                print(result)
        except Exception as e:
            print(f"❌ Failed to call tool '{tool_name}': {e}")
            print("🔄 Resetting connection - try again...")
            # Reset authentication state so user can try again
            await self.cleanup()

    async def interactive_loop(self):
        """Run interactive command loop."""
        print("\n🎯 Interactive MCP Client (Lazy Authentication)")
        print("Commands:")
        print("  list - List available tools (triggers auth if needed)")
        print("  call <tool_name> [args] - Call a tool (triggers auth if needed)")
        print("  status - Show authentication status")
        print("  quit - Exit the client")
        print()
        print("💡 Authentication will only happen when you first use 'list' or 'call'")
        print()

        while True:
            try:
                command = input("mcp> ").strip()

                if not command:
                    continue

                if command == "quit":
                    break

                elif command == "status":
                    if self._authenticated and self.session:
                        print("✅ Authenticated and connected")
                    else:
                        print("🔒 Not authenticated (will authenticate on first tool use)")

                elif command == "list":
                    await self.list_tools()

                elif command.startswith("call "):
                    parts = command.split(maxsplit=2)
                    tool_name = parts[1] if len(parts) > 1 else ""

                    if not tool_name:
                        print("❌ Please specify a tool name")
                        continue

                    # Parse arguments (simple JSON-like format)
                    arguments = {}
                    if len(parts) > 2:
                        import json

                        try:
                            arguments = json.loads(parts[2])
                        except json.JSONDecodeError:
                            print("❌ Invalid arguments format (expected JSON)")
                            continue

                    await self.call_tool(tool_name, arguments)

                else:
                    print(
                        "❌ Unknown command. Try 'list', 'call <tool_name>', 'status', or 'quit'"
                    )

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                await self.cleanup()
                break
            except EOFError:
                await self.cleanup()
                break


async def main():
    """Main entry point."""
    # Default server URL - can be overridden with environment variable
    # Most MCP streamable HTTP servers use /mcp as the endpoint
    server_port = os.getenv("MCP_SERVER_PORT", "8080") 
    transport_type = os.getenv("MCP_TRANSPORT_TYPE", "streamable_http")
    
    # Build the server URL based on your MCP server configuration
    if transport_type == "streamable_http":
        server_url = f"http://localhost:{server_port}/mcp"
    else:
        server_url = f"http://localhost:{server_port}/sse"

    print("🚀 Lazy Auth MCP Client")
    print(f"Connecting to: {server_url}")
    print(f"Transport type: {transport_type}")

    # Start connection flow - OAuth will only happen when tools are used
    client = LazyAuthClient(server_url, transport_type)
    await client.connect()


def cli():
    """CLI entry point for uv script."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()