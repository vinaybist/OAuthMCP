# fixed_sms_research_server.py
from mcp.server.fastmcp import FastMCP
import requests
from tavily import TavilyClient
from typing import List, Dict
from dotenv import load_dotenv
import os

# Create server
mcp = FastMCP("mcp_server", host="0.0.0.0", port=8080)

# Init tavily 
load_dotenv()

# Check
if "TV_API_KEY" not in os.environ:
    raise Exception("TV_API_KEY env is not set...")

# Get key
TV_API_KEY = os.environ["TV_API_KEY"]
tv_client = TavilyClient(TV_API_KEY)  # Fixed typo

@mcp.tool()
def send_text(phone: str, message: str) -> str:
    """Send a text message to a phone number
    
    Args:
        phone: Phone number (e.g., 5551234567)
        message: Text message to send
    """
    try:
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
            return f"Text sent to {phone}"
        else:
            return f"Failed: {result.get('error', 'Unknown error')}"
            
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def web_search(query: str) -> Dict:
    """Use this tool to do web search.

    Args:
        query: Search query.

    Returns:
        Dict with search results.
    """
    try:
        response = tv_client.search(query)
        
        # Return the full response as a dict (not just results list)
        return {
            "query": response.get("query", query),
            "answer": response.get("answer"),
            "results": response.get("results", []),
            "response_time": response.get("response_time"),
            "total_results": len(response.get("results", []))
        }
        
    except Exception as e:
        return {
            "error": f"Search failed: {str(e)}",
            "query": query,
            "results": []
        }

@mcp.resource("sms://test/message")
def get_test_message_resource():
    """Get a test message resource (no auth required for testing)"""
    import datetime
    return f"Test SMS Resource - Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

# Run the server
if __name__ == "__main__":
    print("Starting SMS & Research MCP Server...")
    print("SMS: TextBelt | Search: Tavily | Host: 0.0.0.0:8080")
    mcp.run(transport="streamable-http")