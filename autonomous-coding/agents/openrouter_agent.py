"""
OpenRouter Agent
================

Implementation of the coding agent interface using OpenRouter API.
OpenRouter provides access to multiple AI models through a unified API.

Includes browser automation via Playwright for UI testing.
"""

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx

from .base import AgentConfig, AgentResponse, BaseCodingAgent

# Import logger - use try/except for when module is imported standalone
try:
    from logging_util import log
except ImportError:
    # Fallback to print if logging_util not available
    def log(message: str, end: str = "\n", flush: bool = False) -> None:
        print(message, end=end, flush=flush)

# Try to import Playwright (optional dependency)
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    Page = None


# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Tool definitions for autonomous coding
CODING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_read_files",
            "description": "Read multiple files at once (more efficient than multiple read_file calls)",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of file paths to read (e.g., ['src/App.tsx', 'src/types.ts'])"
                    }
                },
                "required": ["paths"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_server",
            "description": "Manage the development server (start, stop, restart, or check status)",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "restart", "status"],
                        "description": "Action to perform: start, stop, restart, or status"
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to start the server (default: npm run dev). Only used with start/restart."
                    }
                },
                "required": ["action"]
            }
        }
    },
    # Browser automation tools (Puppeteer-compatible)
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate the browser to a URL. Launches browser if not already running.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to navigate to (e.g., 'http://localhost:3000')"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Take a screenshot of the current page. Returns base64-encoded image data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "Whether to capture the full scrollable page (default: false)"
                    },
                    "selector": {
                        "type": "string",
                        "description": "Optional CSS selector to screenshot a specific element"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element on the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector of the element to click (e.g., 'button.submit', '#login-btn')"
                    }
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "Fill an input field with text",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector of the input element (e.g., 'input[name=email]', '#password')"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to fill into the input"
                    }
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_evaluate",
            "description": "Execute JavaScript code in the browser context and return the result",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "JavaScript code to execute (e.g., 'document.title', 'document.querySelectorAll(\"li\").length')"
                    }
                },
                "required": ["script"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_close",
            "description": "Close the browser instance",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]

# Default allowed commands (subset for security)
# Should match the commands in security.py for consistency
DEFAULT_ALLOWED_COMMANDS = {
    # File inspection
    "ls", "cat", "head", "tail", "wc", "grep", "find",
    # File operations
    "cp", "mkdir", "chmod",
    # Directory
    "pwd",
    # Node.js
    "npm", "node",
    # Version control
    "git",
    # Process management
    "ps", "lsof", "sleep", "pkill",
}


class OpenRouterAgent(BaseCodingAgent):
    """
    Coding agent implementation using OpenRouter API.

    OpenRouter provides access to multiple AI models (Claude, GPT-4, Llama, etc.)
    through a unified OpenAI-compatible API.

    Prerequisites:
        - Set OPENROUTER_API_KEY environment variable
    """

    def __init__(self, config: AgentConfig):
        """Initialize the OpenRouter agent."""
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._messages: list[dict] = []
        
        # Track background server process
        self._server_process: Optional[asyncio.subprocess.Process] = None
        self._server_command: Optional[str] = None
        
        # Browser automation (Playwright)
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._screenshots_dir: Optional[Path] = None

        # Use default allowed commands if not specified
        if not config.allowed_commands:
            config.allowed_commands = DEFAULT_ALLOWED_COMMANDS.copy()

    @property
    def name(self) -> str:
        return "OpenRouter"

    @property
    def supported_models(self) -> list[str]:
        # OpenRouter supports many models - these are popular coding models
        return [
            "anthropic/claude-sonnet-4",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "openai/gpt-4-turbo",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3.1-405b-instruct",
            "deepseek/deepseek-coder",
            "mistralai/codestral-latest",
        ]

    def _get_api_key(self) -> str:
        """Get API key from config or environment."""
        api_key = self.config.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable not set.\n"
                "Get your API key from: https://openrouter.ai/keys"
            )
        return api_key

    def _validate_command(self, command: str) -> tuple[bool, str]:
        """Validate a shell command against the allowlist."""
        # Extract the base command
        parts = command.strip().split()
        if not parts:
            return False, "Empty command"

        base_cmd = parts[0]

        # Check if command is in allowlist
        if base_cmd not in self.config.allowed_commands:
            return False, f"Command '{base_cmd}' not in allowed list"

        return True, ""

    async def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool and return the result."""
        project_dir = self.config.project_dir

        try:
            if tool_name == "read_file":
                path_arg = arguments.get("path")
                if not path_arg:
                    return "Error: 'path' parameter is required"
                file_path = project_dir / path_arg
                if not file_path.exists():
                    return f"Error: File not found: {path_arg}"
                # Security: ensure file is within project directory
                if not str(file_path.resolve()).startswith(str(project_dir.resolve())):
                    return "Error: Access denied - file outside project directory"
                return file_path.read_text()

            elif tool_name == "batch_read_files":
                # Read multiple files in one call for efficiency
                paths = arguments.get("paths", [])
                if not paths:
                    return "Error: 'paths' parameter is required (array of file paths)"
                
                results = []
                for path_arg in paths[:10]:  # Limit to 10 files per batch
                    file_path = project_dir / path_arg
                    if not file_path.exists():
                        results.append(f"=== {path_arg} ===\nError: File not found")
                    elif not str(file_path.resolve()).startswith(str(project_dir.resolve())):
                        results.append(f"=== {path_arg} ===\nError: Access denied")
                    else:
                        try:
                            content = file_path.read_text()
                            # Truncate very large files
                            if len(content) > 5000:
                                content = content[:5000] + "\n... (truncated, file too large)"
                            results.append(f"=== {path_arg} ===\n{content}")
                        except Exception as e:
                            results.append(f"=== {path_arg} ===\nError: {e}")
                
                return "\n\n".join(results)

            elif tool_name == "write_file":
                path_arg = arguments.get("path")
                content_arg = arguments.get("content")
                if not path_arg:
                    return "Error: 'path' parameter is required"
                if content_arg is None:
                    return "Error: 'content' parameter is required"
                file_path = project_dir / path_arg
                # Security: ensure file is within project directory
                if not str(file_path.resolve()).startswith(str(project_dir.resolve())):
                    return "Error: Access denied - file outside project directory"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content_arg)
                return f"Successfully wrote to {path_arg}"

            elif tool_name == "run_command":
                command = arguments.get("command")
                if not command:
                    return "Error: 'command' parameter is required"
                # Validate command
                valid, error = self._validate_command(command)
                if not valid:
                    return f"Error: Command blocked - {error}"

                # Check if this is a dev server command (runs indefinitely)
                dev_server_patterns = [
                    "npm run dev", "npm start", "npm run start",
                    "node server", "node app", "node index",
                    "npx next dev", "npx vite",
                    "yarn dev", "yarn start",
                ]
                is_dev_server = any(pattern in command for pattern in dev_server_patterns)

                # Execute command
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(project_dir),
                )

                if is_dev_server:
                    # For dev servers, wait briefly for startup then return
                    try:
                        # Wait up to 10 seconds for some output
                        await asyncio.sleep(3)  # Give server time to start
                        
                        # Check if process is still running (good - server started)
                        if process.returncode is None:
                            # Store the process for later management
                            self._server_process = process
                            self._server_command = command
                            return (
                                f"Dev server started in background with command: {command}\n"
                                "Server is running. You can now test the application.\n"
                                "Use manage_server tool with action 'stop' to stop, 'restart' to restart, or 'status' to check."
                            )
                        else:
                            # Process exited quickly - probably an error
                            stdout, stderr = await process.communicate()
                            result = stdout.decode() if stdout else ""
                            if stderr:
                                result += f"\nStderr: {stderr.decode()}"
                            return f"Dev server exited immediately:\n{result}"
                    except Exception as e:
                        return f"Dev server may have started. Error checking status: {e}"
                else:
                    # For regular commands, use timeout
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            process.communicate(),
                            timeout=60.0  # 60 second timeout for regular commands
                        )
                        result = stdout.decode() if stdout else ""
                        if stderr:
                            result += f"\nStderr: {stderr.decode()}"
                        if process.returncode != 0:
                            result += f"\nExit code: {process.returncode}"
                        return result or "(no output)"
                    except asyncio.TimeoutError:
                        process.kill()
                        return f"Command timed out after 60 seconds: {command}"

            elif tool_name == "list_directory":
                path_arg = arguments.get("path", ".")
                dir_path = project_dir / path_arg
                if not dir_path.exists():
                    return f"Error: Directory not found: {path_arg}"
                # Security: ensure directory is within project directory
                if not str(dir_path.resolve()).startswith(str(project_dir.resolve())):
                    return "Error: Access denied - directory outside project directory"
                files = list(dir_path.iterdir())
                if not files:
                    return "(empty directory)"
                return "\n".join(f.name for f in sorted(files))

            elif tool_name == "manage_server":
                action = arguments.get("action", "").lower()
                command = arguments.get("command", "npm run dev")
                
                if action == "status":
                    if self._server_process is None:
                        return "No server is currently tracked. Use action 'start' to start a server."
                    
                    if self._server_process.returncode is None:
                        return (
                            f"Server is RUNNING\n"
                            f"Command: {self._server_command}\n"
                            f"PID: {self._server_process.pid}"
                        )
                    else:
                        return (
                            f"Server has STOPPED (exit code: {self._server_process.returncode})\n"
                            f"Last command: {self._server_command}"
                        )
                
                elif action == "stop":
                    if self._server_process is None:
                        return "No server is currently running."
                    
                    if self._server_process.returncode is not None:
                        return "Server has already stopped."
                    
                    # Try graceful termination first
                    self._server_process.terminate()
                    try:
                        await asyncio.wait_for(self._server_process.wait(), timeout=5.0)
                        result = f"Server stopped gracefully (was running: {self._server_command})"
                    except asyncio.TimeoutError:
                        # Force kill if graceful termination fails
                        self._server_process.kill()
                        await self._server_process.wait()
                        result = f"Server force-killed (was running: {self._server_command})"
                    
                    self._server_process = None
                    self._server_command = None
                    return result
                
                elif action == "start":
                    # Stop existing server if running
                    if self._server_process is not None and self._server_process.returncode is None:
                        self._server_process.terminate()
                        try:
                            await asyncio.wait_for(self._server_process.wait(), timeout=5.0)
                        except asyncio.TimeoutError:
                            self._server_process.kill()
                            await self._server_process.wait()
                    
                    # Start new server
                    process = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(project_dir),
                    )
                    
                    await asyncio.sleep(3)  # Give server time to start
                    
                    if process.returncode is None:
                        self._server_process = process
                        self._server_command = command
                        return (
                            f"Server started successfully!\n"
                            f"Command: {command}\n"
                            f"PID: {process.pid}\n"
                            "Server is running in background."
                        )
                    else:
                        stdout, stderr = await process.communicate()
                        return f"Server failed to start:\n{stdout.decode()}\n{stderr.decode()}"
                
                elif action == "restart":
                    # Stop existing server
                    if self._server_process is not None and self._server_process.returncode is None:
                        old_command = self._server_command
                        self._server_process.terminate()
                        try:
                            await asyncio.wait_for(self._server_process.wait(), timeout=5.0)
                        except asyncio.TimeoutError:
                            self._server_process.kill()
                            await self._server_process.wait()
                        
                        # Use old command if no new command specified
                        if command == "npm run dev" and old_command:
                            command = old_command
                    
                    # Start new server
                    process = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(project_dir),
                    )
                    
                    await asyncio.sleep(3)
                    
                    if process.returncode is None:
                        self._server_process = process
                        self._server_command = command
                        return (
                            f"Server restarted successfully!\n"
                            f"Command: {command}\n"
                            f"PID: {process.pid}"
                        )
                    else:
                        stdout, stderr = await process.communicate()
                        return f"Server failed to restart:\n{stdout.decode()}\n{stderr.decode()}"
                
                else:
                    return f"Error: Unknown action '{action}'. Use: start, stop, restart, or status"

            # ========================================
            # Browser automation tools
            # ========================================
            elif tool_name == "browser_navigate":
                if not PLAYWRIGHT_AVAILABLE:
                    return "Error: Playwright not installed. Run: pip install playwright && playwright install chromium"
                
                url = arguments.get("url", "")
                if not url:
                    return "Error: 'url' parameter is required"
                
                # Launch browser if not already running
                if self._browser is None:
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(headless=True)
                    self._page = await self._browser.new_page()
                    self._screenshots_dir = project_dir / "screenshots"
                    self._screenshots_dir.mkdir(exist_ok=True)
                
                await self._page.goto(url, wait_until="networkidle", timeout=30000)
                title = await self._page.title()
                return f"Navigated to {url}\nPage title: {title}"

            elif tool_name == "browser_screenshot":
                if self._page is None:
                    return "Error: Browser not open. Use browser_navigate first."
                
                full_page = arguments.get("full_page", False)
                selector = arguments.get("selector")
                
                try:
                    if selector:
                        element = await self._page.query_selector(selector)
                        if element is None:
                            return f"Error: Element not found: {selector}"
                        screenshot_bytes = await element.screenshot()
                    else:
                        screenshot_bytes = await self._page.screenshot(full_page=full_page)
                    
                    # Save screenshot to file
                    import time
                    filename = f"screenshot_{int(time.time())}.png"
                    screenshot_path = self._screenshots_dir / filename
                    screenshot_path.write_bytes(screenshot_bytes)
                    
                    # Return base64 for potential use in multimodal context
                    b64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
                    return (
                        f"Screenshot saved to: {screenshot_path.relative_to(project_dir)}\n"
                        f"Size: {len(screenshot_bytes)} bytes\n"
                        f"Base64 preview (first 100 chars): {b64_data[:100]}..."
                    )
                except Exception as e:
                    return f"Error taking screenshot: {str(e)}"

            elif tool_name == "browser_click":
                if self._page is None:
                    return "Error: Browser not open. Use browser_navigate first."
                
                selector = arguments.get("selector", "")
                if not selector:
                    return "Error: 'selector' parameter is required"
                
                try:
                    await self._page.click(selector, timeout=10000)
                    await self._page.wait_for_load_state("networkidle", timeout=5000)
                    return f"Clicked element: {selector}"
                except Exception as e:
                    return f"Error clicking element '{selector}': {str(e)}"

            elif tool_name == "browser_fill":
                if self._page is None:
                    return "Error: Browser not open. Use browser_navigate first."
                
                selector = arguments.get("selector", "")
                text = arguments.get("text", "")
                
                if not selector:
                    return "Error: 'selector' parameter is required"
                if not text and text != "":
                    return "Error: 'text' parameter is required"
                
                try:
                    await self._page.fill(selector, text, timeout=10000)
                    return f"Filled '{selector}' with text: {text[:50]}{'...' if len(text) > 50 else ''}"
                except Exception as e:
                    return f"Error filling element '{selector}': {str(e)}"

            elif tool_name == "browser_evaluate":
                if self._page is None:
                    return "Error: Browser not open. Use browser_navigate first."
                
                script = arguments.get("script", "")
                if not script:
                    return "Error: 'script' parameter is required"
                
                try:
                    result = await self._page.evaluate(script)
                    return f"Result: {json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)}"
                except Exception as e:
                    return f"Error evaluating script: {str(e)}"

            elif tool_name == "browser_close":
                if self._browser is None:
                    return "Browser is not open."
                
                try:
                    await self._page.close()
                    await self._browser.close()
                    await self._playwright.stop()
                    self._page = None
                    self._browser = None
                    self._playwright = None
                    return "Browser closed successfully."
                except Exception as e:
                    return f"Error closing browser: {str(e)}"

            else:
                return f"Error: Unknown tool: {tool_name}"

        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    async def connect(self) -> None:
        """Initialize the HTTP client."""
        self._get_api_key()  # Validate API key exists

        self._client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout

        # Ensure project directory exists
        self.config.project_dir.mkdir(parents=True, exist_ok=True)

        # Build enhanced system prompt with tool instructions
        tools_info = """

## AVAILABLE TOOLS

You have access to these tools for file and command operations:

### File & Command Tools

1. **read_file** - Read contents of a file
   - Parameters: `path` (required) - relative path to file
   - Example: {"path": "src/app.js"}

2. **batch_read_files** - Read MULTIPLE files at once (saves tool calls!)
   - Parameters: `paths` (required) - array of file paths
   - Example: {"paths": ["src/App.tsx", "src/types.ts", "src/components/Block.tsx"]}
   - Use this instead of multiple read_file calls!

3. **write_file** - Write content to a file
   - Parameters: `path` (required), `content` (required)
   - Example: {"path": "hello.txt", "content": "Hello World!"}

4. **run_command** - Execute a shell command
   - Parameters: `command` (required)
   - Allowed: ls, cat, head, tail, wc, grep, find (current dir only), cp, mkdir, chmod, pwd, npm, node, git, ps, lsof, sleep, pkill
   - NOT allowed: rm, mv, touch, echo, curl, wget, python, bash, sh, sudo
   - NOTE: For dev servers (npm run dev, etc.), use manage_server tool instead

5. **list_directory** - List files in a directory
   - Parameters: `path` (required) - relative path to directory
   - Example: {"path": "./src"}

6. **manage_server** - Start, stop, restart, or check status of dev server
   - Parameters: `action` (required) - one of: start, stop, restart, status
   - Parameters: `command` (optional) - server start command (default: "npm run dev")
   - Examples:
     - Start: {"action": "start", "command": "npm run dev"}
     - Stop: {"action": "stop"}
     - Restart: {"action": "restart"}
     - Status: {"action": "status"}
   - Use this instead of run_command for dev servers!

### Browser Automation Tools (for UI testing)

6. **browser_navigate** - Navigate browser to a URL (launches browser if needed)
   - Parameters: `url` (required) - URL to navigate to
   - Example: {"url": "http://localhost:3000"}

7. **browser_screenshot** - Take screenshot of current page
   - Parameters: `full_page` (optional, default false), `selector` (optional - CSS selector for element)
   - Examples:
     - Full page: {"full_page": true}
     - Element: {"selector": "#main-content"}
     - Viewport: {}

8. **browser_click** - Click an element
   - Parameters: `selector` (required) - CSS selector
   - Example: {"selector": "button.submit"}

9. **browser_fill** - Fill text into an input field
   - Parameters: `selector` (required), `text` (required)
   - Example: {"selector": "input[name=email]", "text": "user@example.com"}

10. **browser_evaluate** - Execute JavaScript in browser context
    - Parameters: `script` (required) - JavaScript code
    - Examples:
      - Get title: {"script": "document.title"}
      - Count elements: {"script": "document.querySelectorAll('li').length"}
      - Check text: {"script": "document.body.innerText.includes('Welcome')"}

11. **browser_close** - Close the browser
    - Parameters: none
    - Example: {}

IMPORTANT:
- Always provide ALL required parameters for each tool call.
- Use browser tools for UI testing after starting the dev server.
- Take screenshots to verify visual state.
- Close browser when done testing.
"""
        # Initialize messages with system prompt
        self._messages = [
            {
                "role": "system",
                "content": self.config.system_prompt + tools_info
            }
        ]

        self._is_connected = True

    async def disconnect(self) -> None:
        """Close the HTTP client, browser, and stop any running server."""
        # Close browser if open
        if self._browser is not None:
            try:
                if self._page:
                    await self._page.close()
                await self._browser.close()
                if self._playwright:
                    await self._playwright.stop()
            except Exception:
                pass  # Ignore errors during cleanup
            self._page = None
            self._browser = None
            self._playwright = None
        
        # Stop server if running
        if self._server_process is not None and self._server_process.returncode is None:
            self._server_process.terminate()
            try:
                await asyncio.wait_for(self._server_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._server_process.kill()
            self._server_process = None
            self._server_command = None
        
        if self._client:
            await self._client.aclose()
            self._client = None
        self._is_connected = False

    async def _call_api(self, messages: list[dict]) -> dict:
        """Make an API call to OpenRouter."""
        headers = {
            "Authorization": f"Bearer {self._get_api_key()}",
            "HTTP-Referer": "https://github.com/anthropics/claude-quickstarts",
            "X-Title": "Autonomous Coding Agent",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model,
            "messages": messages,
            "tools": CODING_TOOLS,
            "tool_choice": "auto",
            "max_tokens": 4096,
        }

        response = await self._client.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
        )

        if response.status_code != 200:
            error_text = response.text
            raise RuntimeError(f"OpenRouter API error ({response.status_code}): {error_text}")

        return response.json()

    async def run_session(self, prompt: str) -> AgentResponse:
        """Run a single session with OpenRouter."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Agent not connected. Call connect() first.")

        log("Sending prompt to OpenRouter API...\n")

        # Add user message
        self._messages.append({
            "role": "user",
            "content": prompt
        })

        response_text = ""
        tool_calls_made = []
        max_iterations = 100  # Allow enough iterations for full feature cycle

        try:
            for iteration in range(max_iterations):
                # Call API
                result = await self._call_api(self._messages)

                choice = result.get("choices", [{}])[0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "")

                # Get text content
                content = message.get("content", "")
                if content:
                    response_text += content
                    log(content, end="", flush=True)

                # Check for tool calls
                tool_calls = message.get("tool_calls", [])

                if tool_calls:
                    # Add assistant message with tool calls
                    self._messages.append(message)

                    # Process each tool call
                    for tool_call in tool_calls:
                        function = tool_call.get("function", {})
                        tool_name = function.get("name", "")
                        tool_id = tool_call.get("id", "")

                        try:
                            arguments = json.loads(function.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            arguments = {}

                        log(f"\n[Tool: {tool_name}]", flush=True)
                        if arguments:
                            args_str = str(arguments)
                            if len(args_str) > 200:
                                log(f"   Input: {args_str[:200]}...", flush=True)
                            else:
                                log(f"   Input: {args_str}", flush=True)

                        # Execute the tool with timing
                        start_time = time.perf_counter()
                        tool_result = await self._execute_tool(tool_name, arguments)
                        end_time = time.perf_counter()
                        duration_ms = (end_time - start_time) * 1000

                        # Show result summary with duration
                        # Tool errors always start with "Error:" - don't match "Error" in file content
                        is_error = tool_result.startswith("Error:") or tool_result.startswith("Error executing")
                        if is_error:
                            log(f"   [Error] {tool_result[:200]} ({duration_ms:.0f}ms)", flush=True)
                        else:
                            log(f"   [Done] ({duration_ms:.0f}ms)", flush=True)

                        tool_calls_made.append({
                            "name": tool_name,
                            "input": arguments,
                            "output": tool_result[:500] if len(tool_result) > 500 else tool_result,
                            "duration_ms": round(duration_ms, 1),
                        })

                        # Add tool result to messages
                        self._messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": tool_result,
                        })
                    
                    # Mid-session nudge: If many calls but no writes, encourage action
                    write_count = sum(1 for tc in tool_calls_made if tc["name"] == "write_file")
                    call_count = len(tool_calls_made)
                    
                    if call_count == 10 and write_count == 0:
                        nudge_msg = (
                            "\n[System] 💡 You've made 10 tool calls. Remember: this is a continuation session. "
                            "You don't need to re-explore the entire codebase. "
                            "Please start implementing soon - use write_file to create or modify code.\n"
                        )
                        log(nudge_msg, flush=True)
                        self._messages.append({
                            "role": "user",
                            "content": nudge_msg
                        })
                    elif call_count == 20 and write_count == 0:
                        nudge_msg = (
                            "\n[System] ⚠️ 20 tool calls but no files written yet. "
                            "STOP reading files and START implementing! Use write_file NOW. "
                            "Pick the first failing test and write the code to fix it.\n"
                        )
                        log(nudge_msg, flush=True)
                        self._messages.append({
                            "role": "user",
                            "content": nudge_msg
                        })
                    elif call_count == 35 and write_count == 0:
                        nudge_msg = (
                            "\n[System] 🚨 35 tool calls and still no files written! "
                            "This session is being wasted on exploration. "
                            "Use write_file IMMEDIATELY to implement the failing test!\n"
                        )
                        log(nudge_msg, flush=True)
                        self._messages.append({
                            "role": "user",
                            "content": nudge_msg
                        })
                    
                    # Positive reinforcement when agent writes files
                    if write_count == 1 and tool_calls_made[-1]["name"] == "write_file":
                        encourage_msg = (
                            "\n[System] ✅ Great! You wrote a file. Now: "
                            "1) Test it with browser automation "
                            "2) If it works, update feature_list.json (change passes: false to true) "
                            "3) Git commit your changes\n"
                        )
                        log(encourage_msg, flush=True)
                        self._messages.append({
                            "role": "user", 
                            "content": encourage_msg
                        })

                    # Continue the loop to get next response
                    continue

                # No tool calls - check if we're done
                if finish_reason == "stop" or not tool_calls:
                    break
            else:
                # Loop exhausted without natural completion
                log(f"\n[Warning] Reached max iterations ({max_iterations}). Session ending.", flush=True)

            log("\n" + "-" * 70 + "\n")
            
            # Print summary of what was accomplished
            write_calls = sum(1 for tc in tool_calls_made if tc["name"] == "write_file")
            total_duration_ms = sum(tc.get("duration_ms", 0) for tc in tool_calls_made)
            
            if tool_calls_made:
                log(f"[Summary] {len(tool_calls_made)} tool calls, total execution time: {total_duration_ms:.0f}ms")
            
            if write_calls == 0 and len(tool_calls_made) > 10:
                log(f"[Note] Made {len(tool_calls_made)} tool calls but no files were written.")
                log("[Tip] Focus on creating files (feature_list.json, init.sh) rather than just exploring.\n")

            return AgentResponse(
                status="continue",
                text=response_text,
                tool_calls=tool_calls_made,
            )

        except Exception as e:
            log(f"\nError during OpenRouter session: {e}")
            return AgentResponse(
                status="error",
                text=response_text,
                error=str(e),
                tool_calls=tool_calls_made,
            )

    async def stream_session(self, prompt: str) -> AsyncIterator[str]:
        """Stream a session (simplified - OpenRouter streaming is similar to OpenAI)."""
        # For now, use non-streaming and yield the full response
        response = await self.run_session(prompt)
        yield response.text

    def print_config_summary(self) -> None:
        """Print OpenRouter-specific configuration summary."""
        super().print_config_summary()
        log("OpenRouter configuration:")
        log(f"   - API endpoint: {OPENROUTER_API_URL}")
        log(f"   - Model: {self.config.model}")
        log(f"   - Project directory: {self.config.project_dir.resolve()}")
        log(f"   - Allowed commands: {len(self.config.allowed_commands)} commands")
        log(f"   - Browser automation: {'Available (Playwright)' if PLAYWRIGHT_AVAILABLE else 'Not available (pip install playwright)'}")
        log("")

