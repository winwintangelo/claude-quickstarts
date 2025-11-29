"""
Base Coding Agent
=================

Abstract base class defining the interface for all coding agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

# Import logger - use try/except for when module is imported standalone
try:
    from logging_util import log
except ImportError:
    # Fallback to print if logging_util not available
    def log(message: str, end: str = "\n", flush: bool = False) -> None:
        print(message, end=end, flush=flush)


@dataclass
class AgentConfig:
    """Configuration for a coding agent."""

    # Project settings
    project_dir: Path
    model: str

    # Security settings
    allowed_commands: set[str] = field(default_factory=set)
    sandbox_enabled: bool = True

    # Agent-specific settings
    system_prompt: str = "You are an expert full-stack developer building a production-quality web application."
    max_turns: int = 1000

    # Optional API key override (otherwise uses environment variable)
    api_key: Optional[str] = None

    # Additional agent-specific options
    extra_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Response from a coding agent session."""

    # Status of the response
    status: str  # "continue", "complete", "error"

    # Text content of the response
    text: str

    # Tool calls made during the session
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    # Any errors encountered
    error: Optional[str] = None

    # Metadata about the session
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCodingAgent(ABC):
    """
    Abstract base class for coding agents.

    All coding agents (Claude, Codex, etc.) must implement this interface
    to be used with the autonomous coding harness.
    """

    def __init__(self, config: AgentConfig):
        """
        Initialize the coding agent.

        Args:
            config: Agent configuration
        """
        self.config = config
        self._is_connected = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this agent."""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """Return list of supported model identifiers."""
        pass

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the agent service.

        This is called once before running sessions.
        Should handle authentication, client initialization, etc.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to the agent service.

        Called when done with all sessions.
        """
        pass

    @abstractmethod
    async def run_session(self, prompt: str) -> AgentResponse:
        """
        Run a single agent session with the given prompt.

        Args:
            prompt: The prompt to send to the agent

        Returns:
            AgentResponse with status, text, and any tool calls
        """
        pass

    @abstractmethod
    async def stream_session(self, prompt: str) -> AsyncIterator[str]:
        """
        Run a session and stream the response.

        Args:
            prompt: The prompt to send to the agent

        Yields:
            Text chunks as they are received
        """
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    def validate_model(self, model: str) -> bool:
        """Check if a model is supported by this agent."""
        return model in self.supported_models

    def get_default_model(self) -> str:
        """Return the default model for this agent."""
        if self.supported_models:
            return self.supported_models[0]
        raise NotImplementedError("No default model defined")

    def create_settings_file(self) -> Optional[Path]:
        """
        Create agent-specific settings file in the project directory.

        Returns:
            Path to the settings file, or None if not needed
        """
        return None

    def print_config_summary(self) -> None:
        """Print a summary of the agent configuration."""
        log(f"Agent: {self.name}")
        log(f"Model: {self.config.model}")
        log(f"Project: {self.config.project_dir.resolve()}")
        if self.config.sandbox_enabled:
            log("Sandbox: Enabled")
        if self.config.allowed_commands:
            log(f"Allowed commands: {len(self.config.allowed_commands)} commands")

