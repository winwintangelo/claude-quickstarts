# Autonomous Coding Agent - Product Requirements Document

## Overview

The Autonomous Coding Agent is a minimal harness demonstrating long-running autonomous coding with AI coding agents. It implements a **two-agent pattern** (initializer + coding agent) that can build complete applications over multiple sessions.

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                     autonomous_agent_demo.py                         │
│                    (Entry Point + Agent Selection)                   │
│                  --agent claude | --agent codex                      │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           agent.py                                   │
│                    (Agent Session Logic)                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ run_autonomous  │  │ run_agent      │  │ Session Management  │  │
│  │ _agent()        │──│ _session()     │──│ & Auto-continue     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        agents/ Package                               │
│                  (Multi-Agent Abstraction Layer)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ base.py         │  │ claude_agent.py│  │ codex_agent.py      │  │
│  │ BaseCodingAgent │  │ ClaudeCodeAgent│  │ OpenAICodexAgent    │  │
│  │ AgentConfig     │  │                 │  │                     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
┌─────────────────────────────┐  ┌─────────────────────────────────────┐
│      Claude Code SDK        │  │         OpenAI Codex CLI            │
│   (claude-code-sdk package) │  │       (@openai/codex npm)           │
└─────────────────────────────┘  └─────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         security.py                                  │
│                   (Bash Command Validation)                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ Allowed         │  │ Command        │  │ Extra Validation    │  │
│  │ Commands List   │  │ Extraction     │  │ (pkill, chmod)      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Two-Agent Pattern

1. **Initializer Agent (Session 1)**
   - Reads `app_spec.txt` specification
   - Creates `feature_list.json` with 200 test cases
   - Creates `init.sh` setup script
   - Initializes Git repository
   - Sets up project structure

2. **Coding Agent (Sessions 2+)**
   - Picks up where the previous session left off
   - Implements features one by one
   - Tests with browser automation (Puppeteer)
   - Marks tests as passing in `feature_list.json`
   - Commits progress to git

### Session Management

- Each session runs with a **fresh context window**
- Progress persisted via `feature_list.json` and git commits
- Auto-continues between sessions (3 second delay)
- Press `Ctrl+C` to pause; run same command to resume

## Components

### Entry Point (`autonomous_agent_demo.py`)

| Argument | Description | Default |
|----------|-------------|---------|
| `--project-dir` | Directory for the project | `./autonomous_demo_project` |
| `--agent` | Coding agent to use (`claude` or `codex`) | `claude` |
| `--max-iterations` | Max agent iterations | Unlimited |
| `--model` | Model to use | Agent's default |
| `--list-agents` | List available agents and exit | - |

### Agents Package (`agents/`)

The `agents/` package provides a unified interface for different coding agents:

| File | Description |
|------|-------------|
| `__init__.py` | Factory function `get_agent()` and agent registry |
| `base.py` | `BaseCodingAgent` abstract class and `AgentConfig` dataclass |
| `claude_agent.py` | `ClaudeCodeAgent` - Claude Code SDK implementation |
| `codex_agent.py` | `OpenAICodexAgent` - OpenAI Codex CLI implementation |

#### Supported Agents

| Agent | Provider | SDK/CLI | Default Model | Supported Models |
|-------|----------|---------|---------------|------------------|
| `claude` | Anthropic | claude-code-sdk | claude-sonnet-4-5-20250929 | claude-sonnet-4-5-20250929, claude-opus-4-1-20250805, claude-haiku-4-5-20251001 |
| `codex` | OpenAI | @openai/codex | gpt-5.1-codex-max | gpt-5.1-codex-max, o3, o4-mini, gpt-4o, gpt-4o-mini |
| `openrouter` | OpenRouter | REST API | anthropic/claude-sonnet-4 | anthropic/*, openai/*, google/*, meta-llama/*, deepseek/*, mistralai/* |

### Agent Logic (`agent.py`)

- `run_autonomous_agent()` - Main loop managing sessions
- `run_agent_session()` - Single session execution
- Handles session headers, progress tracking, auto-continue

### Agent Configuration

Each agent supports a common `AgentConfig`:

```python
@dataclass
class AgentConfig:
    project_dir: Path          # Project directory
    model: str                 # Model identifier
    allowed_commands: set[str] # Bash command allowlist
    sandbox_enabled: bool      # OS-level sandbox
    system_prompt: str         # Custom system prompt
    max_turns: int             # Max conversation turns
    api_key: Optional[str]     # API key override
    extra_options: dict        # Agent-specific options
```

### Claude Agent Features

Security layers (defense in depth):
1. **OS-level Sandbox** - Bash commands run in isolation
2. **Filesystem Restrictions** - Operations restricted to project directory
3. **Security Hooks** - Bash commands validated against allowlist

Built-in tools:
- Read, Write, Edit, Glob, Grep, Bash

MCP Servers:
- Puppeteer (browser automation for testing)

### Codex Agent Features

- Uses OpenAI Codex CLI (`@openai/codex`)
- Non-interactive mode via `codex exec` subcommand
- Supports `--full-auto` for sandboxed automatic execution
- Authentication: `codex login` (ChatGPT account) OR `OPENAI_API_KEY` env var

### OpenRouter Agent Features

- Uses OpenRouter REST API (OpenAI-compatible)
- Supports 100+ models from multiple providers (Anthropic, OpenAI, Google, Meta, etc.)
- Built-in tool execution: `read_file`, `write_file`, `run_command`, `list_directory`, `manage_server`
- Command validation against security allowlist
- Authentication: `OPENROUTER_API_KEY` env var
- Enhanced system prompt with tool documentation (parameters, examples, allowed commands)
- Dev server management with start/stop/restart/status support
- **Browser automation via Playwright** (parity with Claude's Puppeteer MCP):
  - `browser_navigate` - Navigate to URL, launches browser automatically
  - `browser_screenshot` - Capture screenshots (full page, viewport, or element)
  - `browser_click` - Click elements by CSS selector
  - `browser_fill` - Fill input fields
  - `browser_evaluate` - Execute JavaScript in browser context
  - `browser_close` - Close browser instance
  - Screenshots saved to `screenshots/` directory in project
- **Session management**:
  - Max 100 tool calls per session (enough for full feature cycle)
  - Warns when max iterations reached
  - Reports when sessions explore but don't write files
  - Robust error detection (only matches "Error:" prefix, not file content)
  - **Duration tracking**: Shows execution time in ms for each tool call and total session time
  - **Progressive nudges**: At 10, 20, 35 tool calls without writes, injects increasingly urgent reminders
  - **Positive reinforcement**: Encourages agent after first write_file with next steps
  - **Context-aware prompts**: Includes specific failing tests and tells agent to skip redundant exploration
  - **Dual logging**: All output goes to both stdout AND log files in `{project}/logs/agent_session_{timestamp}.log`
- **Efficiency optimizations**:
  - **Project snapshot in prompt**: Includes directory listing, source structure, git log, progress notes, dev server URL, app spec summary - eliminates need for pwd, ls, cat commands
  - **batch_read_files tool**: Read up to 10 files in one call instead of 10 separate read_file calls
  - **Efficiency tips in prompt**: Guides agent to complete a feature cycle in ~30 calls vs 100
  - **Explicit "DO NOT" list**: Tells agent which commands to skip (pwd, ls, cat, git log, wrong port)
  - **Dev server port auto-detection**: Parses vite.config.ts to include correct URL in snapshot
  - **Auto-completion detection**: Stops agent loop when all tests pass (100% completion)
  - **Vite default port detection**: Correctly identifies port 5173 for Vite projects without explicit config

### Security (`security.py`)

**Allowed Commands:**
| Category | Commands |
|----------|----------|
| File inspection | `ls`, `cat`, `head`, `tail`, `wc`, `grep` |
| File discovery | `find` (current directory only, no `-exec`/`-delete`) |
| File operations | `cp`, `mkdir`, `chmod` (+x only) |
| Directory | `pwd` |
| Node.js | `npm`, `node` |
| Version control | `git` |
| Process management | `ps`, `lsof`, `sleep`, `pkill` (dev processes only) |
| Script execution | `init.sh` |

**Commands with Extra Validation:**
| Command | Validation Rules |
|---------|------------------|
| `find` | Path must start with `.` or `./`; blocks `-exec`, `-execdir`, `-delete`, `-ok` |
| `pkill` | Only dev processes: `node`, `npm`, `npx`, `vite`, `next` |
| `chmod` | Only `+x` mode allowed (e.g., `chmod +x`, `chmod u+x`) |
| `init.sh` | Only `./init.sh` or paths ending in `/init.sh` |

### Progress Tracking (`progress.py`)

- Counts passing/total tests from `feature_list.json`
- Prints session headers and progress summaries

### Prompt Loading (`prompts.py`)

- Loads prompts from `prompts/` directory
- Copies `app_spec.txt` to project directory

## Prompt Templates

### Initializer Prompt (`prompts/initializer_prompt.md`)

Tasks:
1. Read `app_spec.txt` specification
2. Create `feature_list.json` with 200 test cases
3. Create `init.sh` setup script
4. Initialize Git repository
5. Set up project structure
6. Optionally start implementation

Includes:
- **Allowed Bash Commands** section listing permitted commands
- **Browser Automation** brief reference for optional verification

### Coding Prompt (`prompts/coding_prompt.md`)

Steps:
1. **Orient** - Read files, check git history, count remaining tests
2. **Start servers** - Run `init.sh`
3. **Verify** - Test existing passing features for regressions
4. **Choose** - Pick highest-priority failing feature
5. **Implement** - Write code
6. **Test** - Use browser automation (mandatory!)
7. **Update** - Mark test as passing (only change `"passes"` field)
8. **Commit** - Git commit with descriptive message
9. **Progress** - Update `claude-progress.txt`
10. **Clean exit** - Ensure no broken state

Includes:
- **Allowed Bash Commands** section listing permitted commands
- **Browser Automation Tools** section with full tool reference for both agents

### Prompt Security & Tool Guidance

Both prompts now include upfront documentation of:
- Allowed bash commands (ls, cat, grep, find, npm, node, git, etc.)
- Blocked commands (rm, mv, curl, wget, python, sudo, etc.)
- Recommendation to use SDK tools (Read, Write, Edit) over bash for file operations
- **Browser automation tools** for both Claude (Puppeteer) and OpenRouter (Playwright) agents

This reduces wasted API calls from blocked command attempts and ensures agents know how to test UIs.

## Demo Application Spec

Default spec (`prompts/app_spec.txt`) builds a **Claude.ai Clone**:

| Component | Technology |
|-----------|------------|
| Frontend | React + Vite + Tailwind CSS |
| Backend | Node.js + Express + SQLite |
| Database | SQLite with better-sqlite3 |
| Streaming | Server-Sent Events (SSE) |
| API | Claude API via Anthropic SDK |

Features include:
- Streaming chat with markdown rendering
- Artifact detection and rendering
- Conversation management
- Projects and organization
- Model selection
- Settings and customization
- Sharing and collaboration
- Usage tracking

## Dependencies

### Python Dependencies (`requirements.txt`)

```
claude-code-sdk>=0.0.25
httpx>=0.27.0  # For OpenRouter API
```

### System Dependencies

For **OpenAI Codex** agent:
```bash
npm install -g @openai/codex
```

### Environment Variables

**API Keys:**
| Variable | Agent | Description |
|----------|-------|-------------|
| `ANTHROPIC_API_KEY` | Claude | Anthropic API key (required) |
| `OPENAI_API_KEY` | Codex | OpenAI API key (optional if using `codex login`) |
| `OPENROUTER_API_KEY` | OpenRouter | OpenRouter API key (https://openrouter.ai/keys) |

**Model Configuration (optional):**
| Variable | Agent | Default |
|----------|-------|---------|
| `CLAUDE_MODEL` | Claude | `claude-sonnet-4-5-20250929` |
| `CODEX_MODEL` | Codex | `gpt-5.1-codex-max` |
| `OPENROUTER_MODEL` | OpenRouter | `anthropic/claude-sonnet-4` |

All variables can be set in a `.env` file (copy from `env.example`).

### Validation Script (`validate_agent.py`)

Validates agent setup and can run live tests:

```bash
python validate_agent.py                    # Validate all agents (setup only)
python validate_agent.py claude             # Validate Claude agent only
python validate_agent.py codex              # Validate Codex agent only
python validate_agent.py openrouter         # Validate OpenRouter agent only
python validate_agent.py --test codex       # Run live test with Codex (uses API credits)
python validate_agent.py --commands         # Run command tests (OpenRouter only)
python validate_agent.py openrouter --test --commands  # Both test types
```

**Live Test** (`--test`): Creates a temp directory, asks agent to create `hello.txt`, verifies output, cleans up.

**Command Tests** (`--commands`): Comprehensive tool/command tests for OpenRouter agent (~35 tests):

| Category | Tests |
|----------|-------|
| **File Tools** | `write_file`, `read_file`, `list_directory` |
| **Bash - File Inspection** | `ls`, `cat`, `head`, `tail`, `wc`, `grep`, `find` |
| **Bash - File Operations** | `cp`, `mkdir`, `chmod` |
| **Bash - Directory/Git** | `pwd`, `git init`, `git status` |
| **Bash - Process** | `ps`, `sleep` |
| **Server Management** | `manage_server (status)`, `manage_server (start)`, `manage_server (stop)` |
| **Browser Automation** | `browser_navigate`, `browser_screenshot`, `browser_click`, `browser_fill`, `browser_evaluate`, `browser_close` |
| **Security (blocked)** | `rm`, `mv`, `curl`, `wget` |
| **Error Handling** | file not found, directory not found, command exit codes, false positive check (file with "Error" in content) |

## Generated Project Structure

After running, the project directory contains:

```
my_project/
├── feature_list.json         # Test cases (source of truth)
├── app_spec.txt              # Copied specification
├── init.sh                   # Environment setup script
├── claude-progress.txt       # Session progress notes
├── .claude_settings.json     # Security settings
└── [application files]       # Generated application code
```

## Key Design Principles

1. **Defense in depth** - Multiple security layers (sandbox + filesystem + allowlist)
2. **Session persistence** - Progress saved via `feature_list.json` and git commits
3. **Fresh context windows** - Each session starts clean (no memory pollution)
4. **Browser-based testing** - Mandatory Puppeteer verification (no curl-only testing)
5. **Immutable test specs** - Never remove/edit features, only mark as passing

## Usage Examples

### Using Claude (default)
```bash
python autonomous_agent_demo.py --project-dir ./my_project
```

### Using OpenAI Codex
```bash
python autonomous_agent_demo.py --project-dir ./my_project --agent codex
```

### Using OpenRouter (access 100+ models)
```bash
python autonomous_agent_demo.py --project-dir ./my_project --agent openrouter
python autonomous_agent_demo.py --project-dir ./my_project --agent openrouter --model openai/gpt-4o
python autonomous_agent_demo.py --project-dir ./my_project --agent openrouter --model google/gemini-pro-1.5
```

### Specifying a model
```bash
python autonomous_agent_demo.py --project-dir ./my_project --agent claude --model claude-opus-4-1-20250805
```

### Limiting iterations for testing
```bash
python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 3
```

### List available agents
```bash
python autonomous_agent_demo.py --list-agents
```

### Validate agent setup
```bash
python validate_agent.py --test codex      # Live test
python validate_agent.py --commands        # Command tests (OpenRouter)
```

## Future Enhancements

- [x] Support for multiple coding agents (OpenAI Codex)
- [x] Configurable agent backends
- [x] Plugin architecture for custom agents
- [x] Agent validation script with live testing
- [ ] Enhanced progress visualization
- [ ] Parallel feature development
- [ ] Support for additional agents (Cursor, Aider, etc.)

---

*Last Updated: November 2025*

