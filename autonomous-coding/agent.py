"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
Supports multiple coding agents (Claude, Codex, etc.) through a unified interface.
"""

import asyncio
from pathlib import Path
from typing import Optional

from agents import AgentConfig, BaseCodingAgent, get_agent, list_available_agents
from logging_util import init_logger, log, close_logger
from progress import print_session_header, print_progress_summary, count_passing_tests
from prompts import get_initializer_prompt, get_coding_prompt, get_coding_prompt_with_context, copy_spec_to_project


# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3

# Default models for each agent type (can be overridden via environment variables)
DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-5-20250929",
    "codex": "gpt-5.1-codex-max",  # Latest Codex model
    "openrouter": "anthropic/claude-sonnet-4",  # Claude via OpenRouter
}

# Environment variable names for model overrides
MODEL_ENV_VARS = {
    "claude": "CLAUDE_MODEL",
    "codex": "CODEX_MODEL",
    "openrouter": "OPENROUTER_MODEL",
}


def get_default_model(agent_type: str) -> str:
    """
    Get the default model for an agent type.
    
    Checks environment variable first, then falls back to hardcoded default.
    Environment variables: CLAUDE_MODEL, CODEX_MODEL, OPENROUTER_MODEL
    """
    import os
    
    # Check for environment variable override
    env_var = MODEL_ENV_VARS.get(agent_type)
    if env_var:
        env_model = os.environ.get(env_var)
        if env_model:
            return env_model
    
    # Fall back to hardcoded default
    return DEFAULT_MODELS.get(agent_type, DEFAULT_MODELS["claude"])


async def run_agent_session(
    agent: BaseCodingAgent,
    message: str,
    project_dir: Path,
) -> tuple[str, str]:
    """
    Run a single agent session using the provided coding agent.

    Args:
        agent: The coding agent to use
        message: The prompt to send
        project_dir: Project directory path

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    response = await agent.run_session(message)

    if response.status == "error":
        return "error", response.error or "Unknown error"

    return response.status, response.text


async def run_autonomous_agent(
    project_dir: Path,
    agent_type: str = "claude",
    model: Optional[str] = None,
    max_iterations: Optional[int] = None,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        agent_type: Type of coding agent to use ("claude" or "codex")
        model: Model to use (defaults to agent's default model)
        max_iterations: Maximum number of iterations (None for unlimited)
    """
    # Validate agent type
    available_agents = list_available_agents()
    if agent_type not in available_agents:
        print(f"Error: Unknown agent type '{agent_type}'")
        print(f"Available agents: {', '.join(available_agents)}")
        return

    # Use default model if not specified
    if model is None:
        model = get_default_model(agent_type)

    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT DEMO")
    print("=" * 70)
    print(f"\nAgent: {agent_type.upper()}")
    print(f"Project directory: {project_dir}")
    print(f"Model: {model}")
    if max_iterations:
        print(f"Max iterations: {max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Initialize logger
    logger = init_logger(project_dir)
    log(f"Log file: {logger.log_path}")

    # Check if this is a fresh start or continuation
    tests_file = project_dir / "feature_list.json"
    is_first_run = not tests_file.exists()

    if is_first_run:
        print("Fresh start - will use initializer agent")
        print()
        print("=" * 70)
        print("  NOTE: First session takes 10-20+ minutes!")
        print("  The agent is generating 200 detailed test cases.")
        print("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
        print("=" * 70)
        print()
        # Copy the app spec into the project directory for the agent to read
        copy_spec_to_project(project_dir)
    else:
        print("Continuing existing project")
        print_progress_summary(project_dir)

    # Create agent configuration
    config = AgentConfig(
        project_dir=project_dir,
        model=model,
        sandbox_enabled=True,
    )

    # Main loop
    iteration = 0

    while True:
        iteration += 1

        # Check max iterations
        if max_iterations and iteration > max_iterations:
            print(f"\nReached max iterations ({max_iterations})")
            print("To continue, run the script again without --max-iterations")
            break

        # Print session header
        print_session_header(iteration, is_first_run)

        # Create agent instance (fresh context for each session)
        agent = get_agent(agent_type, config)

        # Print agent configuration summary
        agent.print_config_summary()

        # Choose prompt based on session type
        if is_first_run:
            prompt = get_initializer_prompt()
            is_first_run = False  # Only use initializer once
        else:
            # Use context-aware prompt that includes failing tests
            prompt = get_coding_prompt_with_context(project_dir, iteration)

        # Run session with async context manager
        async with agent:
            status, response = await run_agent_session(agent, prompt, project_dir)

        # Check for completion (all tests passing)
        passing, total = count_passing_tests(project_dir)
        if total > 0 and passing == total:
            log(f"\n🎉 ALL TESTS PASSING ({passing}/{total})! Project complete.")
            print_progress_summary(project_dir)
            break

        # Handle status
        if status == "continue":
            print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(project_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        elif status == "error":
            print("\nSession encountered an error")
            print("Will retry with a fresh session...")
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        # Small delay between sessions
        if max_iterations is None or iteration < max_iterations:
            print("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    # Print instructions for running the generated application
    log("\n" + "-" * 70)
    log("  TO RUN THE GENERATED APPLICATION:")
    log("-" * 70)
    log(f"\n  cd {project_dir.resolve()}")
    log("  ./init.sh           # Run the setup script")
    log("  # Or manually:")
    log("  npm install && npm run dev")
    log("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
    log("-" * 70)

    log("\nDone!")
    
    # Close logger
    close_logger()


# Backward compatibility: Keep old function signature working
async def run_autonomous_agent_legacy(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
) -> None:
    """
    Legacy function signature for backward compatibility.
    Uses Claude as the default agent.
    """
    await run_autonomous_agent(
        project_dir=project_dir,
        agent_type="claude",
        model=model,
        max_iterations=max_iterations,
    )
