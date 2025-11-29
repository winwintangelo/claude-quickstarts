# Autonomous Coding Agent Demo

A minimal harness demonstrating long-running autonomous coding with AI coding agents. This demo implements a two-agent pattern (initializer + coding agent) that can build complete applications over multiple sessions.

**Supports multiple agents:** Claude Code SDK and OpenAI Codex CLI.

## Prerequisites

### For Claude Agent (default)

```bash
# Install Claude Code CLI (latest version required)
npm install -g @anthropic-ai/claude-code

# Install Python dependencies
pip install -r requirements.txt

# Set API key (choose one method):
# Option 1: Environment variable
export ANTHROPIC_API_KEY='your-api-key-here'

# Option 2: Create .env file
cp env.example .env
# Then edit .env and add your API keys
```

### For OpenAI Codex Agent

```bash
# Install Codex CLI
npm install -g @openai/codex

# Install Python dependencies
pip install -r requirements.txt

# Authenticate (choose one):
# Option 1: Login with ChatGPT account (recommended)
codex login

# Option 2: Use API key
export OPENAI_API_KEY='your-api-key-here'
```

## Quick Start

### Using Claude (default)
```bash
python autonomous_agent_demo.py --project-dir ./my_project
```

### Using OpenAI Codex
```bash
python autonomous_agent_demo.py --project-dir ./my_project --agent codex
```

### Using OpenRouter (100+ models)
```bash
export OPENROUTER_API_KEY='your-key-here'
python autonomous_agent_demo.py --project-dir ./my_project --agent openrouter
python autonomous_agent_demo.py --project-dir ./my_project --agent openrouter --model openai/gpt-4o
```

### For testing with limited iterations:
```bash
python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 3
```

### List available agents:
```bash
python autonomous_agent_demo.py --list-agents
```

### Validate your setup:
```bash
python validate_agent.py          # Check all agents
python validate_agent.py claude   # Check Claude only
python validate_agent.py codex    # Check Codex only
```

## Important Timing Expectations

> **Warning: This demo takes a long time to run!**

- **First session (initialization):** The agent generates a `feature_list.json` with 200 test cases. This takes several minutes and may appear to hang - this is normal. The agent is writing out all the features.

- **Subsequent sessions:** Each coding iteration can take **5-15 minutes** depending on complexity.

- **Full app:** Building all 200 features typically requires **many hours** of total runtime across multiple sessions.

**Tip:** The 200 features parameter in the prompts is designed for comprehensive coverage. If you want faster demos, you can modify `prompts/initializer_prompt.md` to reduce the feature count (e.g., 20-50 features for a quicker demo).

## How It Works

### Two-Agent Pattern

1. **Initializer Agent (Session 1):** Reads `app_spec.txt`, creates `feature_list.json` with 200 test cases, sets up project structure, and initializes git.

2. **Coding Agent (Sessions 2+):** Picks up where the previous session left off, implements features one by one, and marks them as passing in `feature_list.json`.

### Session Management

- Each session runs with a fresh context window
- Progress is persisted via `feature_list.json` and git commits
- The agent auto-continues between sessions (3 second delay)
- Press `Ctrl+C` to pause; run the same command to resume

## Supported Agents

| Agent | Provider | SDK/CLI | Default Model | Auth |
|-------|----------|---------|---------------|------|
| `claude` | Anthropic | claude-code-sdk | claude-sonnet-4-5-20250929 | `ANTHROPIC_API_KEY` env var |
| `codex` | OpenAI | @openai/codex | gpt-5.1-codex-max | `codex login` OR `OPENAI_API_KEY` env var |
| `openrouter` | OpenRouter | REST API | anthropic/claude-sonnet-4 | `OPENROUTER_API_KEY` env var |

## Security Model

This demo uses a defense-in-depth security approach (see `security.py`):

1. **OS-level Sandbox:** Bash commands run in an isolated environment
2. **Filesystem Restrictions:** File operations restricted to the project directory only
3. **Bash Allowlist:** Only specific commands are permitted:
   - File inspection: `ls`, `cat`, `head`, `tail`, `wc`, `grep`
   - Node.js: `npm`, `node`
   - Version control: `git`
   - Process management: `ps`, `lsof`, `sleep`, `pkill` (dev processes only)

Commands not in the allowlist are blocked by the security hook.

## Project Structure

```
autonomous-coding/
├── autonomous_agent_demo.py  # Main entry point
├── agent.py                  # Agent session logic
├── agents/                   # Multi-agent abstraction layer
│   ├── __init__.py           # Agent factory and registry
│   ├── base.py               # BaseCodingAgent abstract class
│   ├── claude_agent.py       # Claude Code SDK implementation
│   ├── codex_agent.py        # OpenAI Codex CLI implementation
│   └── openrouter_agent.py   # OpenRouter API implementation
├── client.py                 # Claude SDK client configuration (legacy)
├── security.py               # Bash command allowlist and validation
├── progress.py               # Progress tracking utilities
├── prompts.py                # Prompt loading utilities
├── validate_agent.py         # Agent setup validation script
├── prompts/
│   ├── app_spec.txt          # Application specification
│   ├── initializer_prompt.md # First session prompt
│   └── coding_prompt.md      # Continuation session prompt
├── requirements.txt          # Python dependencies
└── PRD.md                    # Product requirements document
```

## Generated Project Structure

After running, your project directory will contain:

```
my_project/
├── feature_list.json         # Test cases (source of truth)
├── app_spec.txt              # Copied specification
├── init.sh                   # Environment setup script
├── claude-progress.txt       # Session progress notes
├── .claude_settings.json     # Security settings (Claude)
├── .codex_config.json        # Config settings (Codex)
└── [application files]       # Generated application code
```

## Running the Generated Application

After the agent completes (or pauses), you can run the generated application:

```bash
cd generations/my_project

# Run the setup script created by the agent
./init.sh

# Or manually (typical for Node.js apps):
npm install
npm run dev
```

The application will typically be available at `http://localhost:3000` or similar (check the agent's output or `init.sh` for the exact URL).

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--project-dir` | Directory for the project | `./autonomous_demo_project` |
| `--agent` | Coding agent to use (`claude` or `codex`) | `claude` |
| `--max-iterations` | Max agent iterations | Unlimited |
| `--model` | Model to use | Agent's default |
| `--list-agents` | List available agents and exit | - |

## Customization

### Changing the Application

Edit `prompts/app_spec.txt` to specify a different application to build.

### Adjusting Feature Count

Edit `prompts/initializer_prompt.md` and change the "200 features" requirement to a smaller number for faster demos.

### Modifying Allowed Commands

Edit `security.py` to add or remove commands from `ALLOWED_COMMANDS`.

### Adding New Agents

1. Create a new file in `agents/` (e.g., `my_agent.py`)
2. Implement `BaseCodingAgent` interface
3. Register in `agents/__init__.py` `AGENT_REGISTRY`

## Troubleshooting

**"Appears to hang on first run"**
This is normal. The initializer agent is generating 200 detailed test cases, which takes significant time. Watch for `[Tool: ...]` output to confirm the agent is working.

**"Command blocked by security hook"**
The agent tried to run a command not in the allowlist. This is the security system working as intended. If needed, add the command to `ALLOWED_COMMANDS` in `security.py`.

**"API key not set"**
Ensure the appropriate API key is exported in your shell environment:
- Claude: `export ANTHROPIC_API_KEY='your-key'`
- Codex: `export OPENAI_API_KEY='your-key'`

**"Codex CLI not found"**
Install the Codex CLI: `npm install -g @openai/codex`

## License

Internal Anthropic use.
