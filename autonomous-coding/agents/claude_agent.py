"""
Claude Code Agent
==================

Implementation of the coding agent interface using Claude Code SDK.
"""

import json
import os
from pathlib import Path
from typing import AsyncIterator, Optional

from .base import AgentConfig, AgentResponse, BaseCodingAgent

# Lazy import to avoid requiring claude-code-sdk when using other agents
ClaudeSDKClient = None
ClaudeCodeOptions = None
HookMatcher = None


def _import_claude_sdk():
    """Lazy import of Claude SDK components."""
    global ClaudeSDKClient, ClaudeCodeOptions, HookMatcher
    if ClaudeSDKClient is None:
        from claude_code_sdk import ClaudeCodeOptions as _ClaudeCodeOptions
        from claude_code_sdk import ClaudeSDKClient as _ClaudeSDKClient
        from claude_code_sdk.types import HookMatcher as _HookMatcher

        ClaudeSDKClient = _ClaudeSDKClient
        ClaudeCodeOptions = _ClaudeCodeOptions
        HookMatcher = _HookMatcher


# Puppeteer MCP tools for browser automation
PUPPETEER_TOOLS = [
    "mcp__puppeteer__puppeteer_navigate",
    "mcp__puppeteer__puppeteer_screenshot",
    "mcp__puppeteer__puppeteer_click",
    "mcp__puppeteer__puppeteer_fill",
    "mcp__puppeteer__puppeteer_select",
    "mcp__puppeteer__puppeteer_hover",
    "mcp__puppeteer__puppeteer_evaluate",
]

# Built-in tools
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
]

# Default allowed commands for the security hook
DEFAULT_ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "grep",
    "cp", "mkdir", "chmod", "pwd",
    "npm", "node",
    "git",
    "ps", "lsof", "sleep", "pkill",
    "init.sh",
}


class ClaudeCodeAgent(BaseCodingAgent):
    """
    Coding agent implementation using Claude Code SDK.

    This agent uses the official Claude Code SDK to interact with Claude
    for autonomous coding tasks.
    """

    def __init__(self, config: AgentConfig):
        """Initialize the Claude Code agent."""
        super().__init__(config)
        _import_claude_sdk()
        self._client: Optional[ClaudeSDKClient] = None
        self._settings_file: Optional[Path] = None

        # Use default allowed commands if not specified
        if not config.allowed_commands:
            config.allowed_commands = DEFAULT_ALLOWED_COMMANDS.copy()

    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def supported_models(self) -> list[str]:
        return [
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-1-20250805",
            "claude-haiku-4-5-20251001",
        ]

    def _get_api_key(self) -> str:
        """Get API key from config or environment."""
        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set.\n"
                "Get your API key from: https://console.anthropic.com/"
            )
        return api_key

    def _create_security_hook(self):
        """Create the bash security hook function."""
        from security import bash_security_hook
        return bash_security_hook

    def create_settings_file(self) -> Path:
        """Create Claude-specific security settings file."""
        security_settings = {
            "sandbox": {
                "enabled": self.config.sandbox_enabled,
                "autoAllowBashIfSandboxed": True,
            },
            "permissions": {
                "defaultMode": "acceptEdits",
                "allow": [
                    "Read(./**)",
                    "Write(./**)",
                    "Edit(./**)",
                    "Glob(./**)",
                    "Grep(./**)",
                    "Bash(*)",
                    *PUPPETEER_TOOLS,
                ],
            },
        }

        self.config.project_dir.mkdir(parents=True, exist_ok=True)
        settings_file = self.config.project_dir / ".claude_settings.json"

        with open(settings_file, "w") as f:
            json.dump(security_settings, f, indent=2)

        self._settings_file = settings_file
        return settings_file

    async def connect(self) -> None:
        """Initialize the Claude SDK client."""
        # Validate API key
        self._get_api_key()

        # Create settings file
        settings_file = self.create_settings_file()

        # Create client
        self._client = ClaudeSDKClient(
            options=ClaudeCodeOptions(
                model=self.config.model,
                system_prompt=self.config.system_prompt,
                allowed_tools=[
                    *BUILTIN_TOOLS,
                    *PUPPETEER_TOOLS,
                ],
                mcp_servers={
                    "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}
                },
                hooks={
                    "PreToolUse": [
                        HookMatcher(
                            matcher="Bash",
                            hooks=[self._create_security_hook()],
                        ),
                    ],
                },
                max_turns=self.config.max_turns,
                cwd=str(self.config.project_dir.resolve()),
                settings=str(settings_file.resolve()),
            )
        )

        # Enter the async context
        await self._client.__aenter__()
        self._is_connected = True

    async def disconnect(self) -> None:
        """Close the Claude SDK client."""
        if self._client and self._is_connected:
            await self._client.__aexit__(None, None, None)
            self._is_connected = False

    async def run_session(self, prompt: str) -> AgentResponse:
        """Run a single session with Claude."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Agent not connected. Call connect() first.")

        print("Sending prompt to Claude Code SDK...\n")

        try:
            await self._client.query(prompt)

            response_text = ""
            tool_calls = []

            async for msg in self._client.receive_response():
                msg_type = type(msg).__name__

                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__

                        if block_type == "TextBlock" and hasattr(block, "text"):
                            response_text += block.text
                            print(block.text, end="", flush=True)

                        elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                            tool_call = {
                                "name": block.name,
                                "input": getattr(block, "input", {}),
                            }
                            tool_calls.append(tool_call)
                            print(f"\n[Tool: {block.name}]", flush=True)

                            if hasattr(block, "input"):
                                input_str = str(block.input)
                                if len(input_str) > 200:
                                    print(f"   Input: {input_str[:200]}...", flush=True)
                                else:
                                    print(f"   Input: {input_str}", flush=True)

                elif msg_type == "UserMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__

                        if block_type == "ToolResultBlock":
                            result_content = getattr(block, "content", "")
                            is_error = getattr(block, "is_error", False)

                            if "blocked" in str(result_content).lower():
                                print(f"   [BLOCKED] {result_content}", flush=True)
                            elif is_error:
                                error_str = str(result_content)[:500]
                                print(f"   [Error] {error_str}", flush=True)
                            else:
                                print("   [Done]", flush=True)

            print("\n" + "-" * 70 + "\n")

            return AgentResponse(
                status="continue",
                text=response_text,
                tool_calls=tool_calls,
            )

        except Exception as e:
            print(f"Error during Claude session: {e}")
            return AgentResponse(
                status="error",
                text="",
                error=str(e),
            )

    async def stream_session(self, prompt: str) -> AsyncIterator[str]:
        """Stream a session with Claude."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Agent not connected. Call connect() first.")

        await self._client.query(prompt)

        async for msg in self._client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                        yield block.text

    def print_config_summary(self) -> None:
        """Print Claude-specific configuration summary."""
        super().print_config_summary()
        print("Security layers:")
        print("   - Sandbox enabled (OS-level bash isolation)")
        print(f"   - Filesystem restricted to: {self.config.project_dir.resolve()}")
        print("   - Bash commands restricted to allowlist (see security.py)")
        print("   - MCP servers: puppeteer (browser automation)")
        print()

