#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding with AI agents.
This script implements the two-agent pattern (initializer + coding agent) and
supports multiple coding agents (Claude Code SDK, OpenAI Codex, etc.).

Example Usage:
    # Use Claude (default)
    python autonomous_agent_demo.py --project-dir ./my_project

    # Use OpenAI Codex
    python autonomous_agent_demo.py --project-dir ./my_project --agent codex

    # Limit iterations for testing
    python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 5
"""

import argparse
import asyncio
import os
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, skip

from agent import run_autonomous_agent, get_default_model
from agents import list_available_agents


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    available_agents = list_available_agents()

    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent Demo - Long-running agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Start fresh project with Claude (default)
  python autonomous_agent_demo.py --project-dir ./my_project

  # Use OpenAI Codex instead
  python autonomous_agent_demo.py --project-dir ./my_project --agent codex

  # Use a specific model
  python autonomous_agent_demo.py --project-dir ./my_project --model claude-sonnet-4-5-20250929

  # Limit iterations for testing
  python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 5

  # Continue existing project
  python autonomous_agent_demo.py --project-dir ./my_project

Available agents: {', '.join(available_agents)}

Environment Variables:
  ANTHROPIC_API_KEY    Your Anthropic API key (required for Claude)
  OPENAI_API_KEY       Your OpenAI API key (required for Codex)
        """,
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("./autonomous_demo_project"),
        help="Directory for the project (default: generations/autonomous_demo_project). "
        "Relative paths automatically placed in generations/ directory.",
    )

    parser.add_argument(
        "--agent",
        type=str,
        choices=available_agents,
        default="claude",
        help=f"Coding agent to use (default: claude). Available: {', '.join(available_agents)}",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (default: agent's default model)",
    )

    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List available coding agents and exit",
    )

    return parser.parse_args()


def check_api_key(agent_type: str) -> bool:
    """Check if the required API key is set for the agent type."""
    if agent_type == "claude":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Error: ANTHROPIC_API_KEY environment variable not set")
            print("\nGet your API key from: https://console.anthropic.com/")
            print("\nThen set it:")
            print("  export ANTHROPIC_API_KEY='your-api-key-here'")
            return False
    elif agent_type == "codex":
        # Codex supports two auth methods: API key OR 'codex login'
        if not os.environ.get("OPENAI_API_KEY"):
            codex_config_dir = Path.home() / ".codex"
            if not codex_config_dir.exists():
                print("Warning: No OpenAI authentication found.")
                print("\nPlease authenticate using one of these methods:")
                print("\n  Option 1: Run 'codex login' to sign in with ChatGPT account")
                print("\n  Option 2: Set OPENAI_API_KEY environment variable:")
                print("    export OPENAI_API_KEY='your-api-key-here'")
                print("    Get your key from: https://platform.openai.com/api-keys")
                print("\nContinuing anyway (Codex may prompt for login)...")
    elif agent_type == "openrouter":
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("Error: OPENROUTER_API_KEY environment variable not set")
            print("\nGet your API key from: https://openrouter.ai/keys")
            print("\nThen set it:")
            print("  export OPENROUTER_API_KEY='your-api-key-here'")
            return False
    return True


def print_agent_info():
    """Print information about available agents."""
    print("\nAvailable Coding Agents:")
    print("=" * 50)

    print("\n1. Claude (claude)")
    print("   - Provider: Anthropic")
    print("   - SDK: claude-code-sdk")
    print("   - Default model: claude-sonnet-4-5-20250929")
    print("   - Supported models: claude-sonnet-4-5-20250929, claude-opus-4-1-20250805, claude-haiku-4-5-20251001")
    print("   - Requires: ANTHROPIC_API_KEY")

    print("\n2. Codex (codex)")
    print("   - Provider: OpenAI")
    print("   - CLI: @openai/codex")
    print("   - Default model: gpt-5.1-codex-max")
    print("   - Supported models: gpt-5.1-codex-max, o3, o4-mini, gpt-4o, gpt-4o-mini")
    print("   - Auth: 'codex login' OR OPENAI_API_KEY env var")
    print("   - Install: npm install -g @openai/codex")

    print("\n3. OpenRouter (openrouter)")
    print("   - Provider: OpenRouter (multi-model gateway)")
    print("   - API: OpenAI-compatible REST API")
    print("   - Default model: anthropic/claude-sonnet-4")
    print("   - Supported models: anthropic/claude-*, openai/gpt-*, google/gemini-*, meta-llama/*, deepseek/*, mistralai/*")
    print("   - Auth: OPENROUTER_API_KEY env var")
    print("   - Get key: https://openrouter.ai/keys")

    print("\n" + "=" * 50)


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Handle --list-agents
    if args.list_agents:
        print_agent_info()
        return

    # Check for API key
    if not check_api_key(args.agent):
        return

    # Automatically place projects in generations/ directory unless already specified
    project_dir = args.project_dir
    if not str(project_dir).startswith("generations/"):
        # Convert relative paths to be under generations/
        if project_dir.is_absolute():
            # If absolute path, use as-is
            pass
        else:
            # Prepend generations/ to relative paths
            project_dir = Path("generations") / project_dir

    # Use default model if not specified
    model = args.model
    if model is None:
        model = get_default_model(args.agent)

    # Run the agent
    try:
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                agent_type=args.agent,
                model=model,
                max_iterations=args.max_iterations,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
