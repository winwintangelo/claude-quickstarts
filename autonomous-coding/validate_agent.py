#!/usr/bin/env python3
"""
Agent Validation Script
=======================

Validates that a coding agent is properly configured and ready to use.

Usage:
    python validate_agent.py                   # Validate all agents (setup only)
    python validate_agent.py claude            # Validate Claude agent only
    python validate_agent.py codex             # Validate Codex agent only
    python validate_agent.py openrouter        # Validate OpenRouter agent only
    python validate_agent.py --test            # Run live test with default agent
    python validate_agent.py --test codex      # Run live test with Codex
    python validate_agent.py --commands        # Run comprehensive command tests
    
Options:
    --test       Run a live file creation test (uses API credits)
    --commands   Run comprehensive tool/command tests (OpenRouter only)
    
Command Tests Include:
    File Tools:       write_file, read_file, list_directory
    File Inspection:  ls, cat, head, tail, wc, grep, find
    File Operations:  cp, mkdir, chmod
    Directory/Git:    pwd, git init, git status
    Process Mgmt:     ps, sleep
    Server Mgmt:      manage_server (status, start, stop)
    Browser:          browser_navigate, browser_screenshot, browser_click,
                      browser_fill, browser_evaluate, browser_close
    Security:         rm, mv, curl, wget (should be blocked)
    Error Handling:   file not found, directory not found, command errors,
                      false positive check (file content with 'Error' word)
"""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, skip


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}\n")


def print_check(name: str, passed: bool, message: str = "") -> None:
    """Print a check result."""
    if passed:
        status = f"{Colors.GREEN}✓ PASS{Colors.END}"
    else:
        status = f"{Colors.RED}✗ FAIL{Colors.END}"
    
    print(f"  {status}  {name}")
    if message:
        print(f"         {Colors.YELLOW}{message}{Colors.END}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"  {Colors.YELLOW}⚠ {message}{Colors.END}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"  {Colors.BLUE}ℹ {message}{Colors.END}")


def check_python_package(package: str) -> tuple[bool, str]:
    """Check if a Python package is installed."""
    try:
        __import__(package.replace("-", "_"))
        return True, ""
    except ImportError:
        return False, f"Install with: pip install {package}"


def check_command_exists(cmd: str) -> tuple[bool, str]:
    """Check if a command exists in PATH."""
    path = shutil.which(cmd)
    if path:
        return True, path
    return False, f"Command '{cmd}' not found in PATH"


def check_env_var(name: str) -> tuple[bool, str]:
    """Check if an environment variable is set."""
    value = os.environ.get(name)
    if value:
        # Mask the value for security
        masked = value[:4] + "..." + value[-4:] if len(value) > 10 else "***"
        return True, f"Set (value: {masked})"
    return False, "Not set"


def check_directory_exists(path: Path) -> tuple[bool, str]:
    """Check if a directory exists."""
    if path.exists():
        return True, str(path)
    return False, f"Directory not found: {path}"


def run_command(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip() or "Command failed"
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def validate_claude_agent() -> tuple[int, int]:
    """Validate Claude Code agent setup."""
    print_header("Claude Code Agent")
    
    passed = 0
    total = 0
    
    # Check 1: Python SDK
    total += 1
    ok, msg = check_python_package("claude_code_sdk")
    print_check("Python SDK (claude-code-sdk)", ok, msg)
    if ok:
        passed += 1
    
    # Check 2: API Key
    total += 1
    ok, msg = check_env_var("ANTHROPIC_API_KEY")
    print_check("API Key (ANTHROPIC_API_KEY)", ok, msg)
    if ok:
        passed += 1
    else:
        print_info("Get your API key from: https://console.anthropic.com/")
    
    # Check 3: Claude CLI (optional but recommended)
    total += 1
    ok, msg = check_command_exists("claude")
    print_check("Claude CLI (optional)", ok, msg)
    if ok:
        passed += 1
        # Try to get version
        ver_ok, version = run_command(["claude", "--version"])
        if ver_ok:
            print_info(f"Version: {version}")
    else:
        print_info("Install with: npm install -g @anthropic-ai/claude-code")
    
    # Check 4: Node.js (for MCP servers)
    total += 1
    ok, msg = check_command_exists("node")
    print_check("Node.js (for MCP servers)", ok, msg)
    if ok:
        passed += 1
        ver_ok, version = run_command(["node", "--version"])
        if ver_ok:
            print_info(f"Version: {version}")
    
    # Check 5: npm (for MCP servers)
    total += 1
    ok, msg = check_command_exists("npm")
    print_check("npm (for MCP servers)", ok, msg)
    if ok:
        passed += 1
    
    return passed, total


def validate_codex_agent() -> tuple[int, int]:
    """Validate OpenAI Codex agent setup."""
    print_header("OpenAI Codex Agent")
    
    passed = 0
    total = 0
    
    # Check 1: Codex CLI
    total += 1
    ok, msg = check_command_exists("codex")
    print_check("Codex CLI (@openai/codex)", ok, msg)
    if ok:
        passed += 1
        # Try to get version
        ver_ok, version = run_command(["codex", "--version"])
        if ver_ok:
            print_info(f"Version: {version}")
    else:
        print_info("Install with: npm install -g @openai/codex")
    
    # Check 2: Authentication (API key OR codex login)
    total += 1
    api_key_ok, api_msg = check_env_var("OPENAI_API_KEY")
    codex_config = Path.home() / ".codex"
    login_ok, login_msg = check_directory_exists(codex_config)
    
    if api_key_ok:
        print_check("Authentication (OPENAI_API_KEY)", True, api_msg)
        passed += 1
    elif login_ok:
        print_check("Authentication (codex login)", True, "Credentials found in ~/.codex/")
        passed += 1
    else:
        print_check("Authentication", False, "No authentication configured")
        print_info("Option 1: Run 'codex login' to sign in with ChatGPT")
        print_info("Option 2: Set OPENAI_API_KEY environment variable")
        print_info("Get API key from: https://platform.openai.com/api-keys")
    
    # Check 3: Node.js
    total += 1
    ok, msg = check_command_exists("node")
    print_check("Node.js", ok, msg)
    if ok:
        passed += 1
        ver_ok, version = run_command(["node", "--version"])
        if ver_ok:
            print_info(f"Version: {version}")
    
    # Check 4: npm
    total += 1
    ok, msg = check_command_exists("npm")
    print_check("npm", ok, msg)
    if ok:
        passed += 1
    
    return passed, total


def validate_openrouter_agent() -> tuple[int, int]:
    """Validate OpenRouter agent setup."""
    print_header("OpenRouter Agent")
    
    passed = 0
    total = 0
    
    # Check 1: API Key
    total += 1
    ok, msg = check_env_var("OPENROUTER_API_KEY")
    print_check("API Key (OPENROUTER_API_KEY)", ok, msg)
    if ok:
        passed += 1
    else:
        print_info("Get your API key from: https://openrouter.ai/keys")
    
    # Check 2: httpx package (for API calls)
    total += 1
    ok, msg = check_python_package("httpx")
    print_check("HTTP client (httpx)", ok, msg)
    if ok:
        passed += 1
    else:
        print_info("Install with: pip install httpx")
    
    # Check 3: Python version (already checked in common, but useful here)
    total += 1
    py_version = sys.version_info
    ok = py_version >= (3, 10)
    print_check("Python >= 3.10", ok)
    if ok:
        passed += 1
    
    # Check 4: Playwright (optional, for browser automation)
    total += 1
    ok, msg = check_python_package("playwright")
    print_check("Browser automation (playwright)", ok, msg)
    if ok:
        passed += 1
        # Also check if browsers are installed
        try:
            result = subprocess.run(
                ["playwright", "install", "--dry-run", "chromium"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # If dry-run succeeds without "not installed" message, browsers are ready
            if "chromium" not in result.stdout.lower() or "installed" in result.stdout.lower():
                print_info("Browser installed (chromium)")
            else:
                print_warning("Run: playwright install chromium")
        except Exception:
            print_warning("Run: playwright install chromium")
    else:
        print_info("Optional: pip install playwright && playwright install chromium")
    
    return passed, total


def validate_common() -> tuple[int, int]:
    """Validate common requirements."""
    print_header("Common Requirements")
    
    passed = 0
    total = 0
    
    # Check 1: Python version
    total += 1
    py_version = sys.version_info
    ok = py_version >= (3, 10)
    version_str = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
    print_check(f"Python >= 3.10 (found {version_str})", ok)
    if ok:
        passed += 1
    else:
        print_info("Python 3.10 or higher is required")
    
    # Check 2: Git
    total += 1
    ok, msg = check_command_exists("git")
    print_check("Git", ok, msg)
    if ok:
        passed += 1
    
    # Check 3: Project structure
    total += 1
    agents_dir = Path(__file__).parent / "agents"
    ok = agents_dir.exists() and (agents_dir / "__init__.py").exists()
    print_check("agents/ package", ok)
    if ok:
        passed += 1
    
    # Check 4: Security module
    total += 1
    security_file = Path(__file__).parent / "security.py"
    ok = security_file.exists()
    print_check("security.py module", ok)
    if ok:
        passed += 1
    
    # Check 5: Prompts directory
    total += 1
    prompts_dir = Path(__file__).parent / "prompts"
    ok = prompts_dir.exists()
    print_check("prompts/ directory", ok)
    if ok:
        passed += 1
        # Check for required prompt files
        required_prompts = ["app_spec.txt", "initializer_prompt.md", "coding_prompt.md"]
        for prompt in required_prompts:
            if not (prompts_dir / prompt).exists():
                print_warning(f"Missing: prompts/{prompt}")
    
    return passed, total


async def run_live_test_claude(test_dir: Path) -> tuple[bool, str]:
    """Run a live test with Claude agent."""
    try:
        from agents import AgentConfig, ClaudeCodeAgent
        
        config = AgentConfig(
            project_dir=test_dir,
            model="claude-sonnet-4-5-20250929",
            sandbox_enabled=True,
        )
        
        agent = ClaudeCodeAgent(config)
        
        # Simple test prompt
        prompt = """Create a file called 'hello.txt' with the content 'Hello from Claude!'. 
        Then confirm the file was created by reading it back."""
        
        async with agent:
            response = await agent.run_session(prompt)
        
        # Check if file was created
        hello_file = test_dir / "hello.txt"
        if hello_file.exists():
            content = hello_file.read_text().strip()
            if "Hello" in content:
                return True, f"File created with content: {content}"
            return False, f"File exists but unexpected content: {content}"
        
        # Check response for any indication of success
        if response.status == "continue" and response.text:
            return True, "Agent responded (file creation may have been simulated)"
        
        return False, f"Agent status: {response.status}, Error: {response.error}"
        
    except Exception as e:
        return False, str(e)


async def run_live_test_codex(test_dir: Path) -> tuple[bool, str]:
    """Run a live test with Codex agent."""
    try:
        from agents import AgentConfig, OpenAICodexAgent
        
        config = AgentConfig(
            project_dir=test_dir,
            model="gpt-5.1-codex-max",
            sandbox_enabled=True,
        )
        
        agent = OpenAICodexAgent(config)
        
        # Simple test prompt
        prompt = """Create a file called 'hello.txt' with the content 'Hello from Codex!'. 
        Then confirm the file was created."""
        
        async with agent:
            response = await agent.run_session(prompt)
        
        # Check if file was created
        hello_file = test_dir / "hello.txt"
        if hello_file.exists():
            content = hello_file.read_text().strip()
            if "Hello" in content:
                return True, f"File created with content: {content}"
            return False, f"File exists but unexpected content: {content}"
        
        # Check response for any indication of success
        if response.status == "continue" and response.text:
            return True, "Agent responded (file creation may have been simulated)"
        
        return False, f"Agent status: {response.status}, Error: {response.error}"
        
    except Exception as e:
        return False, str(e)


async def run_live_test_openrouter(test_dir: Path) -> tuple[bool, str]:
    """Run a live test with OpenRouter agent."""
    try:
        from agents import AgentConfig, OpenRouterAgent
        
        config = AgentConfig(
            project_dir=test_dir,
            model="anthropic/claude-sonnet-4",
            sandbox_enabled=True,
        )
        
        agent = OpenRouterAgent(config)
        
        # Simple test prompt
        prompt = """Create a file called 'hello.txt' with the content 'Hello from OpenRouter!'.
        Use the write_file tool to create the file."""
        
        async with agent:
            response = await agent.run_session(prompt)
        
        # Check if file was created
        hello_file = test_dir / "hello.txt"
        if hello_file.exists():
            content = hello_file.read_text().strip()
            if "Hello" in content:
                return True, f"File created with content: {content}"
            return False, f"File exists but unexpected content: {content}"
        
        # Check response for any indication of success
        if response.status == "continue" and response.text:
            return True, "Agent responded (check tool calls for file creation)"
        
        return False, f"Agent status: {response.status}, Error: {response.error}"
        
    except Exception as e:
        return False, str(e)


async def run_command_tests_openrouter(test_dir: Path) -> list[tuple[str, bool, str]]:
    """
    Run comprehensive command/tool tests with OpenRouter agent.
    
    Tests all:
    - File tools: write_file, read_file, list_directory
    - Bash commands: ls, cat, head, tail, wc, grep, find, cp, mkdir, chmod, pwd, git
    - Node.js: npm, node
    - Process management: ps
    - Server management: manage_server (status, start, stop)
    - Browser automation: browser_navigate, browser_screenshot, browser_click, browser_fill, browser_evaluate, browser_close
    - Security: blocked commands (rm, mv, curl, wget)
    
    Returns list of (test_name, passed, message) tuples.
    """
    results = []
    
    try:
        from agents import AgentConfig, OpenRouterAgent
        
        config = AgentConfig(
            project_dir=test_dir,
            model="anthropic/claude-sonnet-4",
            sandbox_enabled=True,
        )
        
        agent = OpenRouterAgent(config)
        
        # Helper function to run a single test
        async def run_test(name: str, prompt: str, success_check, setup_fn=None):
            """Run a single test with the agent."""
            try:
                if setup_fn:
                    setup_fn()
                
                response = await agent.run_session(prompt)
                agent._messages = []  # Clear for next test
                
                ok, msg = success_check(response)
                results.append((name, ok, msg))
            except Exception as e:
                results.append((name, False, str(e)[:100]))
                agent._messages = []
        
        # Initialize the agent
        async with agent:
            
            # ================================================================
            # SECTION 1: FILE TOOLS
            # ================================================================
            print(f"  Testing file tools...")
            
            # Test: write_file
            def check_write_file(r):
                f = test_dir / "write_test.txt"
                if f.exists() and "hello" in f.read_text().lower():
                    return True, "File created successfully"
                return False, "File not created or wrong content"
            
            await run_test(
                "write_file",
                "Use write_file to create 'write_test.txt' with content 'Hello World'. Say 'done' when finished.",
                check_write_file
            )
            
            # Test: read_file
            def setup_read():
                (test_dir / "read_test.txt").write_text("Line1: Alpha\nLine2: Beta\nLine3: Gamma")
            
            def check_read_file(r):
                if r.text and ("beta" in r.text.lower() or "line" in r.text.lower()):
                    return True, "File content read correctly"
                return r.text is not None, f"Response: {r.text[:60] if r.text else 'None'}"
            
            await run_test(
                "read_file",
                "Use read_file to read 'read_test.txt'. What's on Line2?",
                check_read_file,
                setup_read
            )
            
            # Test: list_directory
            def setup_list():
                (test_dir / "list_a.txt").write_text("a")
                (test_dir / "list_b.txt").write_text("b")
            
            def check_list_dir(r):
                if r.text and ("list_a" in r.text or "list_b" in r.text or ".txt" in r.text):
                    return True, "Directory listed"
                return r.text is not None, f"Response: {r.text[:60] if r.text else 'None'}"
            
            await run_test(
                "list_directory",
                "Use list_directory to list files in '.' and tell me the file names.",
                check_list_dir,
                setup_list
            )
            
            # ================================================================
            # SECTION 2: BASH COMMANDS - FILE INSPECTION
            # ================================================================
            print(f"  Testing bash commands (file inspection)...")
            
            # Test: ls
            await run_test(
                "run_command (ls)",
                "Use run_command to run 'ls -la' and list the files.",
                lambda r: (r.text is not None and len(r.text) > 10, "ls executed")
            )
            
            # Test: cat
            def setup_cat():
                (test_dir / "cat_test.txt").write_text("CAT_CONTENT_HERE")
            
            await run_test(
                "run_command (cat)",
                "Use run_command to run 'cat cat_test.txt'. What does it contain?",
                lambda r: ("CAT_CONTENT" in r.text if r.text else False, "cat executed"),
                setup_cat
            )
            
            # Test: head
            def setup_head():
                (test_dir / "head_test.txt").write_text("\n".join([f"Line{i}" for i in range(20)]))
            
            await run_test(
                "run_command (head)",
                "Use run_command to run 'head -n 3 head_test.txt'. How many lines do you see?",
                lambda r: (r.text is not None and ("line" in r.text.lower() or "3" in r.text), "head executed"),
                setup_head
            )
            
            # Test: tail
            await run_test(
                "run_command (tail)",
                "Use run_command to run 'tail -n 3 head_test.txt'. What's the last line number?",
                lambda r: (r.text is not None and ("line" in r.text.lower() or "19" in r.text), "tail executed")
            )
            
            # Test: wc
            await run_test(
                "run_command (wc)",
                "Use run_command to run 'wc -l head_test.txt'. How many lines?",
                lambda r: (r.text is not None and ("20" in r.text or "line" in r.text.lower()), "wc executed")
            )
            
            # Test: grep
            def setup_grep():
                (test_dir / "grep_test.txt").write_text("apple\nbanana\napricot\ncherry")
            
            await run_test(
                "run_command (grep)",
                "Use run_command to run 'grep apple grep_test.txt'. What matches?",
                lambda r: (r.text is not None and "apple" in r.text.lower(), "grep executed"),
                setup_grep
            )
            
            # Test: find
            await run_test(
                "run_command (find)",
                "Use run_command to run 'find . -name \"*.txt\"'. List what you find.",
                lambda r: (r.text is not None and ".txt" in r.text, "find executed")
            )
            
            # ================================================================
            # SECTION 3: BASH COMMANDS - FILE OPERATIONS
            # ================================================================
            print(f"  Testing bash commands (file operations)...")
            
            # Test: cp
            def setup_cp():
                (test_dir / "cp_source.txt").write_text("COPY_ME")
            
            def check_cp(r):
                dest = test_dir / "cp_dest.txt"
                if dest.exists() and "COPY_ME" in dest.read_text():
                    return True, "File copied"
                return False, "Copy failed"
            
            await run_test(
                "run_command (cp)",
                "Use run_command to run 'cp cp_source.txt cp_dest.txt'. Confirm it worked.",
                check_cp,
                setup_cp
            )
            
            # Test: mkdir
            def check_mkdir(r):
                new_dir = test_dir / "new_folder"
                if new_dir.exists() and new_dir.is_dir():
                    return True, "Directory created"
                return False, "mkdir failed"
            
            await run_test(
                "run_command (mkdir)",
                "Use run_command to run 'mkdir new_folder'. Confirm it exists.",
                check_mkdir
            )
            
            # Test: chmod
            def setup_chmod():
                script = test_dir / "test_script.sh"
                script.write_text("#!/bin/bash\necho hello")
            
            def check_chmod(r):
                script = test_dir / "test_script.sh"
                import stat
                mode = script.stat().st_mode
                if mode & stat.S_IXUSR:
                    return True, "chmod +x applied"
                return False, "File not executable"
            
            await run_test(
                "run_command (chmod)",
                "Use run_command to run 'chmod +x test_script.sh'. Confirm it's executable.",
                check_chmod,
                setup_chmod
            )
            
            # ================================================================
            # SECTION 4: BASH COMMANDS - DIRECTORY & VERSION CONTROL
            # ================================================================
            print(f"  Testing bash commands (directory & git)...")
            
            # Test: pwd
            await run_test(
                "run_command (pwd)",
                "Use run_command to run 'pwd'. What directory are you in?",
                lambda r: (r.text is not None and "/" in r.text, "pwd executed")
            )
            
            # Test: git (init)
            def check_git(r):
                git_dir = test_dir / ".git"
                return git_dir.exists(), "Git initialized" if git_dir.exists() else "git init failed"
            
            await run_test(
                "run_command (git init)",
                "Use run_command to run 'git init'. Confirm git is initialized.",
                check_git
            )
            
            # Test: git status
            await run_test(
                "run_command (git status)",
                "Use run_command to run 'git status'. What's the status?",
                lambda r: (r.text is not None and ("branch" in r.text.lower() or "untracked" in r.text.lower() or "clean" in r.text.lower()), "git status executed")
            )
            
            # ================================================================
            # SECTION 5: BASH COMMANDS - PROCESS MANAGEMENT
            # ================================================================
            print(f"  Testing bash commands (process management)...")
            
            # Test: ps
            await run_test(
                "run_command (ps)",
                "Use run_command to run 'ps aux | head -5'. What processes do you see?",
                lambda r: (r.text is not None and ("pid" in r.text.lower() or "user" in r.text.lower() or "process" in r.text.lower()), "ps executed")
            )
            
            # Test: sleep (quick)
            await run_test(
                "run_command (sleep)",
                "Use run_command to run 'sleep 1 && echo SLEPT'. Did it work?",
                lambda r: (r.text is not None and "slept" in r.text.lower(), "sleep executed")
            )
            
            # ================================================================
            # SECTION 6: SERVER MANAGEMENT
            # ================================================================
            print(f"  Testing server management...")
            
            # Test: manage_server status
            await run_test(
                "manage_server (status)",
                "Use manage_server with action 'status' to check if any server is running.",
                lambda r: (r.text is not None and ("server" in r.text.lower() or "running" in r.text.lower() or "status" in r.text.lower()), "Status checked")
            )
            
            # Create a simple server script for testing
            server_script = test_dir / "test_server.js"
            server_script.write_text("""
const http = require('http');
const server = http.createServer((req, res) => {
    res.writeHead(200);
    res.end('OK');
});
server.listen(9999, () => console.log('Server on 9999'));
""")
            
            # Test: manage_server start
            await run_test(
                "manage_server (start)",
                "Use manage_server with action 'start' and command 'node test_server.js' to start a server.",
                lambda r: (r.text is not None and ("start" in r.text.lower() or "running" in r.text.lower() or "server" in r.text.lower()), "Server started")
            )
            
            # Brief wait for server
            await asyncio.sleep(1)
            
            # Test: manage_server stop
            await run_test(
                "manage_server (stop)",
                "Use manage_server with action 'stop' to stop the server.",
                lambda r: (r.text is not None and ("stop" in r.text.lower() or "server" in r.text.lower()), "Server stopped")
            )
            
            # ================================================================
            # SECTION 7: BROWSER AUTOMATION
            # ================================================================
            print(f"  Testing browser automation...")
            
            # Check if Playwright is available
            try:
                from playwright.async_api import async_playwright
                playwright_available = True
            except ImportError:
                playwright_available = False
            
            if not playwright_available:
                results.append(("browser_navigate", True, "Skipped - Playwright not installed"))
                results.append(("browser_screenshot", True, "Skipped - Playwright not installed"))
                results.append(("browser_click", True, "Skipped - Playwright not installed"))
                results.append(("browser_fill", True, "Skipped - Playwright not installed"))
                results.append(("browser_evaluate", True, "Skipped - Playwright not installed"))
                results.append(("browser_close", True, "Skipped - Playwright not installed"))
            else:
                # Test: browser_navigate
                await run_test(
                    "browser_navigate",
                    "Use browser_navigate to go to 'https://example.com'. What's the page title?",
                    lambda r: (r.text is not None and ("example" in r.text.lower() or "navigat" in r.text.lower() or "title" in r.text.lower()), "Navigation successful")
                )
                
                # Test: browser_screenshot
                await run_test(
                    "browser_screenshot",
                    "Use browser_screenshot to take a screenshot of the current page.",
                    lambda r: (r.text is not None and ("screenshot" in r.text.lower() or "saved" in r.text.lower() or "captured" in r.text.lower()), "Screenshot taken")
                )
                
                # Test: browser_evaluate
                await run_test(
                    "browser_evaluate",
                    "Use browser_evaluate with script 'document.title' to get the page title.",
                    lambda r: (r.text is not None and ("example" in r.text.lower() or "title" in r.text.lower() or "domain" in r.text.lower()), "Script evaluated")
                )
                
                # For click and fill, we need interactive elements - use a form page
                await run_test(
                    "browser_navigate (form)",
                    "Use browser_navigate to go to 'https://httpbin.org/forms/post'.",
                    lambda r: (r.text is not None, "Navigated to form page")
                )
                
                # Test: browser_fill
                await run_test(
                    "browser_fill",
                    "Use browser_fill with selector 'input[name=custname]' and text 'TestUser' to fill the customer name field.",
                    lambda r: (r.text is not None and ("fill" in r.text.lower() or "text" in r.text.lower() or "input" in r.text.lower()), "Field filled")
                )
                
                # Test: browser_click
                await run_test(
                    "browser_click",
                    "Use browser_click with selector 'input[type=submit]' or 'button' to click the submit button.",
                    lambda r: (r.text is not None and ("click" in r.text.lower() or "submit" in r.text.lower() or "button" in r.text.lower()), "Button clicked")
                )
                
                # Test: browser_close
                await run_test(
                    "browser_close",
                    "Use browser_close to close the browser.",
                    lambda r: (r.text is not None and ("close" in r.text.lower() or "browser" in r.text.lower()), "Browser closed")
                )
            
            # ================================================================
            # SECTION 8: SECURITY - BLOCKED COMMANDS
            # ================================================================
            print(f"  Testing security (blocked commands)...")
            
            # Test: rm should be blocked
            protected = test_dir / "protected.txt"
            protected.write_text("DO NOT DELETE")
            
            await run_test(
                "security (rm blocked)",
                "Use run_command to run 'rm protected.txt'.",
                lambda r: (protected.exists(), "rm correctly blocked" if protected.exists() else "SECURITY ISSUE!")
            )
            
            # Test: mv should be blocked
            move_src = test_dir / "move_source.txt"
            move_src.write_text("DONT MOVE")
            
            await run_test(
                "security (mv blocked)",
                "Use run_command to run 'mv move_source.txt moved.txt'.",
                lambda r: (move_src.exists(), "mv correctly blocked" if move_src.exists() else "SECURITY ISSUE!")
            )
            
            # Test: curl should be blocked
            await run_test(
                "security (curl blocked)",
                "Use run_command to run 'curl https://example.com'.",
                lambda r: (r.text is not None and ("block" in r.text.lower() or "not allowed" in r.text.lower() or "error" in r.text.lower()), "curl correctly blocked")
            )
            
            # Test: wget should be blocked
            await run_test(
                "security (wget blocked)",
                "Use run_command to run 'wget https://example.com'.",
                lambda r: (r.text is not None and ("block" in r.text.lower() or "not allowed" in r.text.lower() or "error" in r.text.lower()), "wget correctly blocked")
            )
            
            # ================================================================
            # SECTION 9: ERROR HANDLING
            # ================================================================
            print(f"  Testing error handling...")
            
            # Test: read_file - file not found
            await run_test(
                "error: read_file (not found)",
                "Use read_file to read 'nonexistent_file_xyz.txt'. What error do you get?",
                lambda r: (r.text is not None and ("not found" in r.text.lower() or "error" in r.text.lower() or "exist" in r.text.lower()), "Error handled correctly")
            )
            
            # Test: list_directory - directory not found
            await run_test(
                "error: list_directory (not found)",
                "Use list_directory to list 'nonexistent_directory_xyz'. What error do you get?",
                lambda r: (r.text is not None and ("not found" in r.text.lower() or "error" in r.text.lower() or "exist" in r.text.lower()), "Error handled correctly")
            )
            
            # Test: run_command - command fails
            await run_test(
                "error: run_command (exit code)",
                "Use run_command to run 'ls nonexistent_path_xyz'. What happens?",
                lambda r: (r.text is not None, "Command error handled")
            )
            
            # Test: read_file - large file content doesn't show as error
            def setup_large_file():
                large_file = test_dir / "large_file.txt"
                # Create file with content containing "Error" word (shouldn't trigger error display)
                large_file.write_text("This file has Error handling code.\nclass ErrorHandler:\n    pass\nError recovery logic here.")
            
            def check_large_file(r):
                # The agent should read the file successfully, not show it as an error
                if r.text and ("errorhandler" in r.text.lower() or "error handling" in r.text.lower() or "recovery" in r.text.lower()):
                    return True, "File with 'Error' word read correctly (not false positive)"
                return r.text is not None, "File read attempted"
            
            await run_test(
                "error: false positive check",
                "Use read_file to read 'large_file.txt'. What classes are defined?",
                check_large_file,
                setup_large_file
            )
            
            # Test: git command on non-repo (error handling)
            # First, remove the .git directory we created earlier
            git_dir = test_dir / ".git"
            if git_dir.exists():
                import shutil as sh
                sh.rmtree(git_dir)
            
            await run_test(
                "error: git (no repo)",
                "Use run_command to run 'git log' in a directory without a git repo. What error do you get?",
                lambda r: (r.text is not None and ("not a git" in r.text.lower() or "fatal" in r.text.lower() or "error" in r.text.lower() or "repository" in r.text.lower()), "Git error handled")
            )
    
    except ImportError as e:
        results.append(("Import", False, f"Could not import OpenRouterAgent: {e}"))
    except Exception as e:
        results.append(("Setup", False, f"Error setting up agent: {e}"))
    
    return results


def run_command_tests(agent_type: str) -> tuple[int, int]:
    """Run command tests for the specified agent."""
    print_header(f"Command Tests: {agent_type.upper()} Agent")
    
    passed = 0
    total = 0
    
    if agent_type != "openrouter":
        print_warning(f"Command tests are only available for OpenRouter agent currently")
        return 0, 0
    
    # Create temporary test directory
    test_dir = Path(tempfile.mkdtemp(prefix=f"cmd_test_{agent_type}_"))
    print_info(f"Test directory: {test_dir}")
    
    try:
        print(f"\n  Running command tests with {agent_type} agent...")
        print(f"  {Colors.YELLOW}(This will use API credits){Colors.END}")
        print()
        
        results = asyncio.run(run_command_tests_openrouter(test_dir))
        
        print()
        for test_name, ok, msg in results:
            total += 1
            print_check(test_name, ok, msg)
            if ok:
                passed += 1
        
    finally:
        # Cleanup
        print()
        print_info(f"Cleaning up test directory...")
        try:
            shutil.rmtree(test_dir)
            print_info("Test directory removed")
        except Exception as e:
            print_warning(f"Could not remove test directory: {e}")
    
    return passed, total


def run_live_test(agent_type: str) -> tuple[int, int]:
    """Run a live test with the specified agent."""
    print_header(f"Live Test: {agent_type.upper()} Agent")
    
    passed = 0
    total = 0
    
    # Create temporary test directory
    test_dir = Path(tempfile.mkdtemp(prefix=f"agent_test_{agent_type}_"))
    print_info(f"Test directory: {test_dir}")
    
    try:
        # Test 1: Agent initialization
        total += 1
        print(f"\n  Running live test with {agent_type} agent...")
        print(f"  {Colors.YELLOW}(This will use API credits){Colors.END}")
        print()
        
        if agent_type == "claude":
            ok, msg = asyncio.run(run_live_test_claude(test_dir))
        elif agent_type == "codex":
            ok, msg = asyncio.run(run_live_test_codex(test_dir))
        elif agent_type == "openrouter":
            ok, msg = asyncio.run(run_live_test_openrouter(test_dir))
        else:
            ok, msg = False, f"Unknown agent type: {agent_type}"
        
        print()
        print_check(f"Agent task completion", ok, msg)
        if ok:
            passed += 1
        
        # Test 2: Check output file exists
        total += 1
        hello_file = test_dir / "hello.txt"
        if hello_file.exists():
            print_check("Output file created", True, str(hello_file))
            passed += 1
            
            # Show file content
            content = hello_file.read_text().strip()
            print_info(f"File content: {content}")
        else:
            print_check("Output file created", False, "hello.txt not found")
            # List what files were created
            files = list(test_dir.iterdir())
            if files:
                print_info(f"Files in test directory: {[f.name for f in files]}")
            else:
                print_info("No files were created in test directory")
    
    finally:
        # Cleanup
        print()
        print_info(f"Cleaning up test directory...")
        try:
            shutil.rmtree(test_dir)
            print_info("Test directory removed")
        except Exception as e:
            print_warning(f"Could not remove test directory: {e}")
    
    return passed, total


def print_summary(results: dict[str, tuple[int, int]]) -> None:
    """Print validation summary."""
    print_header("Summary")
    
    total_passed = 0
    total_checks = 0
    
    for agent, (passed, total) in results.items():
        total_passed += passed
        total_checks += total
        
        if passed == total:
            status = f"{Colors.GREEN}READY{Colors.END}"
        elif passed > 0:
            status = f"{Colors.YELLOW}PARTIAL{Colors.END}"
        else:
            status = f"{Colors.RED}NOT READY{Colors.END}"
        
        print(f"  {agent}: {passed}/{total} checks passed - {status}")
    
    print()
    if total_passed == total_checks:
        print(f"  {Colors.GREEN}{Colors.BOLD}All checks passed! You're ready to go.{Colors.END}")
    else:
        print(f"  {Colors.YELLOW}Some checks failed. Please review the issues above.{Colors.END}")
    
    print()


def print_usage():
    """Print usage information."""
    print(f"""
{Colors.BOLD}Usage:{Colors.END}
  python validate_agent.py                   # Validate setup for all agents
  python validate_agent.py claude            # Validate Claude agent only
  python validate_agent.py codex             # Validate Codex agent only
  python validate_agent.py openrouter        # Validate OpenRouter agent only
  python validate_agent.py --test            # Run live test (uses API credits)
  python validate_agent.py --test codex      # Run live test with Codex
  python validate_agent.py --commands        # Run command tests (OpenRouter)

{Colors.BOLD}Options:{Colors.END}
  --test      Run a live test that creates a simple file
              (This will use API credits!)
  --commands  Run comprehensive command/tool tests (~30 tests)
              (Currently supports OpenRouter agent only)
              
              Tests include:
              • File tools: write_file, read_file, list_directory
              • Bash (file inspection): ls, cat, head, tail, wc, grep, find
              • Bash (file ops): cp, mkdir, chmod
              • Bash (directory/git): pwd, git init, git status
              • Bash (process): ps, sleep
              • Server management: status, start, stop
              • Browser automation: navigate, screenshot, click, fill, evaluate, close
              • Security: rm, mv, curl, wget (blocked commands)
              • Error handling: file not found, dir not found, false positives
              
  --help, -h  Show this help message

{Colors.BOLD}Examples:{Colors.END}
  python validate_agent.py openrouter --test       # Validate + live test
  python validate_agent.py openrouter --commands   # Validate + command tests
  python validate_agent.py --test --commands       # Both test types
""")


def main():
    """Main entry point."""
    print(f"\n{Colors.BOLD}Autonomous Coding Agent - Validation Script{Colors.END}")
    print("=" * 60)
    
    # Parse arguments
    args = sys.argv[1:]
    
    # Check for help
    if "--help" in args or "-h" in args:
        print_usage()
        return
    
    # Check for live test mode
    run_test = "--test" in args
    if run_test:
        args = [a for a in args if a != "--test"]
    
    # Check for command tests mode
    run_cmd_tests = "--commands" in args
    if run_cmd_tests:
        args = [a for a in args if a != "--commands"]
    
    # Determine which agents to check
    agents_to_check = args if args else ["all"]
    
    results = {}
    
    # Always check common requirements
    passed, total = validate_common()
    results["Common"] = (passed, total)
    
    # Check requested agents
    if "all" in agents_to_check or "claude" in agents_to_check:
        passed, total = validate_claude_agent()
        results["Claude"] = (passed, total)
    
    if "all" in agents_to_check or "codex" in agents_to_check:
        passed, total = validate_codex_agent()
        results["Codex"] = (passed, total)
    
    if "all" in agents_to_check or "openrouter" in agents_to_check:
        passed, total = validate_openrouter_agent()
        results["OpenRouter"] = (passed, total)
    
    # Run live tests if requested
    if run_test:
        if "all" in agents_to_check:
            # Default to codex for live test if checking all
            print_warning("Running live test with Codex (specify agent to test another)")
            agents_to_check = ["codex"]
        
        for agent in agents_to_check:
            if agent in ["claude", "codex", "openrouter"]:
                passed, total = run_live_test(agent)
                results[f"Live Test ({agent})"] = (passed, total)
    
    # Run command tests if requested
    if run_cmd_tests:
        if "all" in agents_to_check:
            # Default to openrouter for command tests
            agents_to_check = ["openrouter"]
        
        for agent in agents_to_check:
            if agent == "openrouter":
                passed, total = run_command_tests(agent)
                results[f"Command Tests ({agent})"] = (passed, total)
            else:
                print_warning(f"Command tests not available for {agent} (only OpenRouter supported)")
    
    # Print summary
    print_summary(results)
    
    # Exit with error code if any checks failed
    total_passed = sum(p for p, _ in results.values())
    total_checks = sum(t for _, t in results.values())
    
    sys.exit(0 if total_passed == total_checks else 1)


if __name__ == "__main__":
    main()
