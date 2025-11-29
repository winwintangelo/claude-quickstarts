"""
OpenAI Codex Agent
==================

Implementation of the coding agent interface using OpenAI Codex CLI.
"""

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import AsyncIterator, Optional

from .base import AgentConfig, AgentResponse, BaseCodingAgent


# Default allowed commands for Codex (similar to Claude)
DEFAULT_ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "grep",
    "cp", "mkdir", "chmod", "pwd",
    "npm", "node",
    "git",
    "ps", "lsof", "sleep", "pkill",
    "init.sh",
}


class OpenAICodexAgent(BaseCodingAgent):
    """
    Coding agent implementation using OpenAI Codex CLI.

    This agent uses the OpenAI Codex CLI (@openai/codex) to interact with
    OpenAI's coding models for autonomous coding tasks.

    Prerequisites:
        - Install Codex CLI: npm install -g @openai/codex
        - Set OPENAI_API_KEY environment variable
    """

    def __init__(self, config: AgentConfig):
        """Initialize the OpenAI Codex agent."""
        super().__init__(config)
        self._codex_path: Optional[str] = None
        self._process: Optional[subprocess.Popen] = None

        # Use default allowed commands if not specified
        if not config.allowed_commands:
            config.allowed_commands = DEFAULT_ALLOWED_COMMANDS.copy()

    @property
    def name(self) -> str:
        return "OpenAI Codex"

    @property
    def supported_models(self) -> list[str]:
        # OpenAI Codex supports various OpenAI models
        return [
            "gpt-5.1-codex-max",  # Latest Codex model
            "o3",                  # Reasoning model
            "o4-mini",             # Efficient reasoning model
            "gpt-4o",              # GPT-4o
            "gpt-4o-mini",         # GPT-4o mini
        ]

    def _get_api_key(self) -> str | None:
        """
        Get API key from config or environment.

        Returns None if not set - Codex CLI can also use 'codex login' authentication.
        """
        return self.config.api_key or os.environ.get("OPENAI_API_KEY")

    def _check_authentication(self) -> None:
        """
        Check if authentication is configured.

        Codex CLI supports two authentication methods:
        1. OPENAI_API_KEY environment variable
        2. 'codex login' command (stores credentials locally)
        """
        api_key = self._get_api_key()
        if not api_key:
            # Check if codex login was used (credentials stored in ~/.codex/)
            codex_config_dir = Path.home() / ".codex"
            if not codex_config_dir.exists():
                print(
                    "\nWarning: No OpenAI authentication found.\n"
                    "Please authenticate using one of these methods:\n\n"
                    "  Option 1: Run 'codex login' to sign in with your ChatGPT account\n\n"
                    "  Option 2: Set OPENAI_API_KEY environment variable:\n"
                    "    export OPENAI_API_KEY='your-api-key-here'\n"
                    "    Get your key from: https://platform.openai.com/api-keys\n"
                )

    def _find_codex_cli(self) -> str:
        """Find the Codex CLI executable."""
        # Try to find codex in PATH
        codex_path = shutil.which("codex")
        if codex_path:
            return codex_path

        # Try common npm global paths
        possible_paths = [
            "/usr/local/bin/codex",
            "/opt/homebrew/bin/codex",
            os.path.expanduser("~/.npm-global/bin/codex"),
            os.path.expanduser("~/node_modules/.bin/codex"),
        ]

        for path in possible_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        raise RuntimeError(
            "Codex CLI not found. Please install it with:\n"
            "  npm install -g @openai/codex\n"
            "or:\n"
            "  brew install --cask codex"
        )

    def _build_codex_command(self, prompt: str) -> list[str]:
        """Build the Codex CLI command for non-interactive execution."""
        cmd = [
            self._codex_path,
            "exec",  # Use exec subcommand for non-interactive mode
            "--model", self.config.model,
            "-C", str(self.config.project_dir.resolve()),  # Set working directory
            "--skip-git-repo-check",  # Allow running outside git repo
        ]

        # Add approval mode based on sandbox settings
        if self.config.sandbox_enabled:
            # Use full-auto for sandboxed automatic execution
            cmd.append("--full-auto")
        else:
            # Skip all approvals (dangerous mode)
            cmd.append("--dangerously-bypass-approvals-and-sandbox")

        # Add the prompt at the end
        cmd.append(prompt)

        return cmd

    def create_settings_file(self) -> Path:
        """Create Codex-specific settings file."""
        # Codex uses a different config format
        codex_config = {
            "model": self.config.model,
            "approvalMode": "auto-edit" if self.config.sandbox_enabled else "full-auto",
            "fullAutoErrorMode": "ask-user",
            "notify": False,
            "providers": {
                "openai": {
                    "name": "OpenAI API"
                }
            },
            "history": {
                "persistence": "none",  # Don't persist history across sessions
                "sendMessages": 10,
            },
        }

        self.config.project_dir.mkdir(parents=True, exist_ok=True)
        settings_file = self.config.project_dir / ".codex_config.json"

        with open(settings_file, "w") as f:
            json.dump(codex_config, f, indent=2)

        return settings_file

    async def connect(self) -> None:
        """Initialize the Codex CLI connection."""
        # Check authentication (warns if not configured)
        self._check_authentication()

        # Find Codex CLI
        self._codex_path = self._find_codex_cli()

        # Create settings file
        self.create_settings_file()

        # Ensure project directory exists
        self.config.project_dir.mkdir(parents=True, exist_ok=True)

        self._is_connected = True

    async def disconnect(self) -> None:
        """Close any running Codex processes."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

        self._is_connected = False

    async def run_session(self, prompt: str) -> AgentResponse:
        """Run a single session with Codex CLI."""
        if not self._is_connected:
            raise RuntimeError("Agent not connected. Call connect() first.")

        print("Sending prompt to OpenAI Codex CLI...\n")

        try:
            cmd = self._build_codex_command(prompt)
            env = os.environ.copy()

            # Set API key if available (otherwise Codex uses stored login credentials)
            api_key = self._get_api_key()
            if api_key:
                env["OPENAI_API_KEY"] = api_key

            # Run Codex CLI as a subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.config.project_dir.resolve()),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            response_text = ""
            tool_calls = []

            # Stream stdout
            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8")
                    response_text += decoded
                    print(decoded, end="", flush=True)

                    # Try to parse tool use from output
                    if decoded.strip().startswith("["):
                        try:
                            # Attempt to extract tool information
                            if "running:" in decoded.lower():
                                tool_calls.append({
                                    "name": "shell",
                                    "input": decoded.strip(),
                                })
                        except Exception:
                            pass

            # Wait for completion
            await process.wait()

            # Check for errors
            if process.returncode != 0 and process.stderr:
                stderr = await process.stderr.read()
                error_msg = stderr.decode("utf-8")
                if error_msg:
                    print(f"\n[Error] {error_msg}", flush=True)
                    return AgentResponse(
                        status="error",
                        text=response_text,
                        error=error_msg,
                        tool_calls=tool_calls,
                    )

            print("\n" + "-" * 70 + "\n")

            return AgentResponse(
                status="continue",
                text=response_text,
                tool_calls=tool_calls,
            )

        except FileNotFoundError:
            error = "Codex CLI not found. Please install with: npm install -g @openai/codex"
            print(f"Error: {error}")
            return AgentResponse(
                status="error",
                text="",
                error=error,
            )
        except Exception as e:
            print(f"Error during Codex session: {e}")
            return AgentResponse(
                status="error",
                text="",
                error=str(e),
            )

    async def stream_session(self, prompt: str) -> AsyncIterator[str]:
        """Stream a session with Codex CLI."""
        if not self._is_connected:
            raise RuntimeError("Agent not connected. Call connect() first.")

        cmd = self._build_codex_command(prompt)
        env = os.environ.copy()

        # Set API key if available
        api_key = self._get_api_key()
        if api_key:
            env["OPENAI_API_KEY"] = api_key

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.config.project_dir.resolve()),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if process.stdout:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode("utf-8")

        await process.wait()

    def print_config_summary(self) -> None:
        """Print Codex-specific configuration summary."""
        super().print_config_summary()
        print("Codex CLI configuration:")
        print(f"   - CLI path: {self._codex_path or 'Not yet resolved'}")
        print(f"   - Execution mode: codex exec (non-interactive)")
        print(f"   - Sandbox: {'--full-auto (sandboxed)' if self.config.sandbox_enabled else 'disabled'}")
        print(f"   - Project directory: {self.config.project_dir.resolve()}")
        print()

