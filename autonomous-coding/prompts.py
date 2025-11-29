"""
Prompt Loading Utilities
========================

Functions for loading prompt templates from the prompts directory.
"""

import json
import shutil
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    return prompt_path.read_text()


def get_initializer_prompt() -> str:
    """Load the initializer prompt."""
    return load_prompt("initializer_prompt")


def get_coding_prompt() -> str:
    """Load the coding agent prompt."""
    return load_prompt("coding_prompt")


def get_failing_tests(project_dir: Path, max_tests: int = 3) -> list[dict]:
    """
    Get the first N failing tests from feature_list.json.
    
    Returns list of test dicts with name, description, and steps.
    """
    tests_file = project_dir / "feature_list.json"
    if not tests_file.exists():
        return []
    
    try:
        with open(tests_file, "r") as f:
            tests = json.load(f)
        
        failing = [t for t in tests if not t.get("passes", False)]
        return failing[:max_tests]
    except (json.JSONDecodeError, IOError):
        return []


def get_project_snapshot(project_dir: Path) -> str:
    """
    Generate a snapshot of the project state to include in the prompt.
    
    This eliminates the need for the agent to run pwd, ls, cat commands.
    """
    import subprocess
    
    snapshot_parts = []
    
    # Current directory
    snapshot_parts.append(f"📁 Project Directory: {project_dir.resolve()}")
    
    # Detect dev server port from vite.config or package.json
    port = None
    vite_config = project_dir / "vite.config.ts"
    if vite_config.exists():
        try:
            content = vite_config.read_text()
            import re
            match = re.search(r'port:\s*(\d+)', content)
            if match:
                port = int(match.group(1))
        except:
            pass
    
    # Only show port if we're confident about it
    if port:
        snapshot_parts.append(f"🌐 Dev Server URL: http://localhost:{port}")
    else:
        # Check if it's a Vite project (default 5173) or other
        if vite_config.exists() or (project_dir / "vite.config.js").exists():
            snapshot_parts.append(f"🌐 Dev Server URL: http://localhost:5173 (Vite default)")
        elif (project_dir / "package.json").exists():
            snapshot_parts.append(f"🌐 Dev Server URL: Check package.json scripts for port")
    
    # Directory listing
    try:
        files = sorted(project_dir.iterdir())
        file_list = []
        for f in files:
            if f.name.startswith('.'):
                continue  # Skip hidden files
            if f.is_dir():
                file_list.append(f"  📂 {f.name}/")
            else:
                size = f.stat().st_size
                file_list.append(f"  📄 {f.name} ({size} bytes)")
        if file_list:
            snapshot_parts.append("📋 Project Files:\n" + "\n".join(file_list[:20]))
    except Exception:
        pass
    
    # Source directory structure
    src_dir = project_dir / "src"
    if src_dir.exists():
        try:
            src_files = []
            for root, dirs, files in (project_dir / "src").walk():
                # Skip node_modules
                dirs[:] = [d for d in dirs if d != 'node_modules']
                rel_root = root.relative_to(project_dir)
                for f in files:
                    src_files.append(f"  {rel_root / f}")
            if src_files:
                snapshot_parts.append("📂 Source Structure:\n" + "\n".join(src_files[:30]))
        except Exception:
            pass
    
    # Git log (recent commits)
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            snapshot_parts.append("📝 Recent Commits:\n" + result.stdout.strip())
    except Exception:
        pass
    
    # Progress file content
    progress_file = project_dir / "claude-progress.txt"
    if progress_file.exists():
        try:
            content = progress_file.read_text()
            if len(content) > 500:
                content = content[:500] + "..."
            snapshot_parts.append("📊 Progress Notes:\n" + content)
        except Exception:
            pass
    
    # App spec summary (first 50 lines)
    app_spec = project_dir / "app_spec.txt"
    if app_spec.exists():
        try:
            content = app_spec.read_text()
            lines = content.split('\n')[:50]
            snapshot_parts.append("📋 App Spec (first 50 lines):\n" + '\n'.join(lines))
        except Exception:
            pass
    
    return "\n\n".join(snapshot_parts)


def get_coding_prompt_with_context(project_dir: Path, session_num: int = 1) -> str:
    """
    Load the coding prompt with added context about failing tests AND project snapshot.
    
    This helps the agent focus on specific work rather than exploring.
    The snapshot eliminates need for pwd, ls, cat commands.
    """
    base_prompt = load_prompt("coding_prompt")
    
    # Get project snapshot (eliminates exploration)
    snapshot = get_project_snapshot(project_dir)
    
    # Get failing tests
    failing_tests = get_failing_tests(project_dir)
    
    # Count passing/total
    tests_file = project_dir / "feature_list.json"
    passing, total = 0, 0
    if tests_file.exists():
        try:
            with open(tests_file, "r") as f:
                tests = json.load(f)
            total = len(tests)
            passing = sum(1 for t in tests if t.get("passes", False))
        except:
            pass
    
    # Build context
    context = f"""

---

## 📊 PROJECT SNAPSHOT (No need to run pwd, ls, cat - it's all here!)

{snapshot}

## 📈 Progress: {passing}/{total} tests passing ({(passing/total*100) if total else 0:.0f}%)

"""
    
    if failing_tests:
        context += f"""## 🎯 PRIORITY FOR SESSION {session_num}

Pick ONE of these failing tests to implement:

"""
        for i, test in enumerate(failing_tests, 1):
            name = test.get("name", test.get("description", "Unknown"))
            desc = test.get("description", "")
            steps = test.get("steps", [])
            
            context += f"### {i}. {name}\n"
            if desc and desc != name:
                context += f"**Description:** {desc}\n"
            if steps:
                context += "**Test Steps:**\n"
                for step in steps[:5]:
                    context += f"  - {step}\n"
            context += "\n"
    
    context += """
## 🚫 DO NOT RUN THESE COMMANDS (already in snapshot above!)

- ❌ `pwd` - Directory is shown above  
- ❌ `ls -la` - Files are listed above
- ❌ `cat app_spec.txt` - Read it from snapshot or use batch_read_files
- ❌ `cat feature_list.json` - Failing tests are listed above
- ❌ `cat claude-progress.txt` - Progress notes are shown above
- ❌ `git log` - Recent commits are shown above
- ❌ `browser_navigate` to port 5173 - Use the URL shown in snapshot!

## ⚡ OPTIMAL WORKFLOW (Complete in ~30 calls)

1. `manage_server` action="start" (if not running)
2. `browser_navigate` to the URL shown in snapshot (NOT 5173!)
3. `batch_read_files` for any source files you need
4. `write_file` to implement the fix
5. `browser_navigate` + `browser_screenshot` to verify
6. `write_file` to update feature_list.json
7. `run_command` git add . && git commit

**START NOW: Use the snapshot above. Don't explore. Write code!**
"""
    
    return base_prompt + context


def copy_spec_to_project(project_dir: Path) -> None:
    """Copy the app spec file into the project directory for the agent to read."""
    spec_source = PROMPTS_DIR / "app_spec.txt"
    spec_dest = project_dir / "app_spec.txt"
    if not spec_dest.exists():
        shutil.copy(spec_source, spec_dest)
        print("Copied app_spec.txt to project directory")
