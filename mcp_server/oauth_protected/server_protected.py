#!/usr/bin/env python3
"""
OAuth Protected SMS & Research MCP Server

Your existing SMS and research functionality with OAuth authentication added.
Run with: python server_protected.py
"""

import datetime
import logging
import os
import sys
from typing import Dict

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient

# Import the auth configuration helper
try:
    from auth_config import setup_auth_for_server
except ImportError:
    print("Error: auth_config.py not found in the current directory")
    print("Make sure auth_config.py is in the same folder as this script")
    sys.exit(1)

logger = logging.getLogger(__name__)


# ==========================================
# GLOBAL SERVER INSTANCE FOR MCP INSPECTOR
# ==========================================

# Create global server instance for MCP dev inspector
mcp = None  # Will be initialized in create_sms_research_server()


def create_sms_research_server(host: str = "0.0.0.0", port: int = 8080) -> FastMCP:
    """Create your SMS & Research MCP server with OAuth protection."""
    
    global mcp  # Use global variable for MCP inspector
    
    logger.info("🏗️  Creating SMS & Research MCP server...")
    
    # Create FastMCP server - auth will be configured separately
    mcp = FastMCP(
        name="OAuth Protected SMS & Research Server",
        instructions="SMS and web research server with OAuth authentication",
        host=host,
        port=port,
        debug=True,
    )

    logger.info(f"✅ FastMCP server created: {type(mcp)}")

    # ==========================================
    # ENVIRONMENT SETUP
    # ==========================================
    
    # Load environment variables
    load_dotenv()

    # Check for Tavily API key
    if "TV_API_KEY" not in os.environ:
        logger.error("❌ TV_API_KEY environment variable is not set")
        raise Exception("TV_API_KEY env is not set...")

    # Get Tavily key and initialize client
    TV_API_KEY = os.environ["TV_API_KEY"]
    tv_client = TavilyClient(TV_API_KEY)
    
    logger.info("✅ Tavily client initialized")

    # ==========================================
    # YOUR BUSINESS LOGIC TOOLS (with OAuth protection)
    # ==========================================

    @mcp.tool()
    def send_text(phone: str, message: str) -> str:
        """
        Send a text message to a phone number.
        
        🔒 This tool requires OAuth authentication.
        
        Args:
            phone: Phone number (e.g., 5551234567)
            message: Text message to send
            
        Returns:
            Status message about the SMS delivery
        """
        try:
            logger.info(f"📱 Sending SMS to {phone[:3]}***{phone[-3:]}")
            
            response = requests.post(
                "https://textbelt.com/text",
                data={
                    "phone": phone,
                    "message": message,
                    "key": "textbelt"
                }
            )
            
            result = response.json()
            
            if result.get("success"):
                success_msg = f"✅ Text sent to {phone}"
                logger.info(success_msg)
                return success_msg
            else:
                error_msg = f"❌ Failed: {result.get('error', 'Unknown error')}"
                logger.warning(error_msg)
                return error_msg
                
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @mcp.tool()
    def web_search(query: str) -> Dict:
        """
        Perform web search using Tavily API.
        
        🔒 This tool requires OAuth authentication.

        Args:
            query: Search query string

        Returns:
            Dictionary containing search results, answer, and metadata
        """
        try:
            logger.info(f"🔍 Searching for: {query}")
            
            response = tv_client.search(query)
            
            # Return the full response as a dict
            result = {
                "query": response.get("query", query),
                "answer": response.get("answer"),
                "results": response.get("results", []),
                "response_time": response.get("response_time"),
                "total_results": len(response.get("results", [])),
                "search_timestamp": datetime.datetime.now().isoformat(),
                "protected": True,
                "auth_required": "OAuth Bearer token"
            }
            
            logger.info(f"✅ Search completed: {result['total_results']} results")
            return result
            
        except Exception as e:
            error_result = {
                "error": f"Search failed: {str(e)}",
                "query": query,
                "results": [],
                "search_timestamp": datetime.datetime.now().isoformat(),
                "protected": True
            }
            logger.error(f"❌ Search failed: {str(e)}")
            return error_result

    @mcp.tool()
    def get_server_status() -> Dict:
        """
        Get the current status of the SMS & Research server.
        
        🔒 This tool requires OAuth authentication.
        
        Returns:
            Dictionary with server status and capabilities
        """
        try:
            # Test Tavily connection
            tavily_status = "connected" if TV_API_KEY else "disconnected"
            
            # Test TextBelt (just check if we can reach it)
            try:
                test_response = requests.get("https://textbelt.com", timeout=5)
                textbelt_status = "reachable" if test_response.status_code == 200 else "unreachable"
            except:
                textbelt_status = "unreachable"
            
            return {
                "server_name": "OAuth Protected SMS & Research Server",
                "status": "running",
                "uptime_since": datetime.datetime.now().isoformat(),
                "services": {
                    "sms": {
                        "provider": "TextBelt",
                        "status": textbelt_status,
                        "endpoint": "https://textbelt.com/text"
                    },
                    "search": {
                        "provider": "Tavily",
                        "status": tavily_status,
                        "api_key_configured": bool(TV_API_KEY)
                    }
                },
                "authentication": "OAuth 2.0 Bearer Token Required",
                "available_tools": ["send_text", "web_search", "get_server_status"],
                "protected": True
            }
            
        except Exception as e:
            logger.error(f"❌ Status check failed: {str(e)}")
            return {
                "error": f"Status check failed: {str(e)}",
                "timestamp": datetime.datetime.now().isoformat(),
                "protected": True
            }

    # ==========================================
    # RESOURCES (with OAuth protection)
    # ==========================================

    @mcp.resource("sms://test/message")
    def get_test_message_resource():
        """
        Get a test message resource.
        
        🔒 This resource requires OAuth authentication.
        """
        return f"🔒 Protected SMS Resource - Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Auth: OAuth Required"

    @mcp.resource("mcp://server/capabilities")
    def get_server_capabilities():
        """
        Get detailed server capabilities and configuration.
        
        🔒 This resource requires OAuth authentication.
        """
        capabilities = {
            "name": "OAuth Protected SMS & Research Server",
            "version": "1.0.0",
            "capabilities": {
                "sms": {
                    "description": "Send SMS messages via TextBelt API",
                    "provider": "TextBelt",
                    "supports_international": True,
                    "rate_limits": "Free tier: 1 message per day per phone number"
                },
                "web_search": {
                    "description": "Advanced web search with AI-powered answers",
                    "provider": "Tavily",
                    "features": ["real-time search", "AI summaries", "source citations"]
                }
            },
            "authentication": {
                "type": "OAuth 2.0",
                "token_type": "Bearer",
                "required_scopes": ["user"]
            },
            "endpoints": {
                "authorization_server": "http://localhost:9000",
                "resource_server": f"http://{host}:{port}"
            },
            "generated_at": datetime.datetime.now().isoformat()
        }
        return str(capabilities)

    # ==========================================
    # END BUSINESS LOGIC
    # ==========================================

    logger.info("🛠️  Registered tools: send_text, web_search, get_server_status")
    logger.info("📁 Registered resources: sms://test/message, mcp://server/capabilities")
    
    return mcp


# ==========================================
# INITIALIZE GLOBAL SERVER FOR MCP INSPECTOR
# ==========================================

# Initialize the global server instance
# This allows MCP inspector to find the server object
mcp = create_sms_research_server()


def main():
    """Main entry point for the OAuth protected SMS & Research server."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="OAuth Protected SMS & Research MCP Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument(
        "--transport",
        default="streamable-http",
        choices=["sse", "streamable-http"],
        help="Transport protocol to use"
    )
    parser.add_argument("--auth-server", default="http://localhost:9000", help="Authorization Server URL")
    parser.add_argument(
        "--oauth-strict",
        action="store_true",
        help="Enable strict OAuth resource validation"
    )
    
    args = parser.parse_args()

    try:
        # Use the global MCP server instance
        logger.info("🏗️  Using global MCP server instance...")
        
        # Verify server was created successfully
        if mcp is None:
            logger.error("❌ Failed to create MCP server - server is None")
            return 1
            
        logger.info(f"✅ MCP server ready: {type(mcp).__name__}")
        
        # Configure OAuth authentication
        logger.info("🔐 Setting up OAuth authentication...")
        setup_auth_for_server(
            app=mcp,
            auth_server_url=args.auth_server,
            resource_server_url=f"http://{args.host}:{args.port}",
            oauth_strict=args.oauth_strict
        )
        
        # Update server host/port if different from defaults
        if args.host != "0.0.0.0" or args.port != 8080:
            logger.info(f"🔧 Updating server host/port to {args.host}:{args.port}")
            mcp.host = args.host
            mcp.port = args.port
        
        # Server startup info
        print("=" * 60)
        print("🚀 OAuth Protected SMS & Research MCP Server")
        print("=" * 60)
        print(f"📡 Server URL: http://{args.host}:{args.port}")
        print(f"🔑 Auth Server: {args.auth_server}")
        print(f"🚛 Transport: {args.transport}")
        print(f"🔒 OAuth Protection: Enabled")
        print("🛠️  Services:")
        print("   📱 SMS: TextBelt API")
        print("   🔍 Search: Tavily API")
        print("🛡️  Authentication: OAuth 2.0 Bearer Token Required")
        print("💡 Connect with OAuth client: python ../mcp_client/lazy_client.py")
        print("⚠️  Simple client will fail (no auth)")
        print("=" * 60)

        # Run the server
        logger.info("🎬 Starting server...")
        mcp.run(transport=args.transport)
        logger.info("Server stopped")
        return 0
        
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
        return 0
    except Exception as e:
        logger.exception(f"❌ Server error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())