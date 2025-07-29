# MCP OAuth

# Create the project from scratch

### Prerequistes: UV MUST installed

## 1. Initialize the Project

```bash
uv init mcp_oauth
cd mcp_oauth
```

## 2. Create and Activate Virtual Environment

```bash
uv venv
source .venv/bin/activate      # on macOS/Linux/WSL
.venv\Scripts\activate       # on Windows
```

## 3. Editor Setup - If using VSCode (Optional)

> **Note:**  
> If using **VSCode**, make sure to select the Python interpreter from the `.venv` environment you created.


## 4. Install Required Libraries

Install the `mcp` and `tavily-python` libraries.  
(For SMS functionality, use the [Textbelt API](https://textbelt.com) — no package installation needed.)

```bash
uv add mcp tavily-python
```

## 5. Create the Server File

Get Tavily API key--> Go to https://app.tavily.com/ and sign up to get free key for testing

create folder mcp_server, mcp_client and local_as

Create a MCP server Python file named "server.py" under mcp_server:

```
server.py
```

## Run the MCP Inspector (by using uv)

```bash
uv add mcp[cli]
# Run the inspector
uv run mcp dev server.py # Replace server.py with your server file name
```


## Protect mcp server

Create a copy of MCP server server.py and rename it to "server_protected.py" under mcp_server folder:


