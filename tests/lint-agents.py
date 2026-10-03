#!/usr/bin/env python3
"""Lint every agent definition in agents/ against the rules Claude Code
actually enforces (October 2026, v2.1.288) plus this repo's own conventions.

Python standard library only. Exit 0 = pass, 1 = findings.
Usage: lint-agents.py [agents-dir]   (defaults to this repo's agents/)

Claude Code SILENTLY skips malformed agent files (no error, the agent just
never appears), and `claude plugin validate` catches only some of the causes,
so this suite exists to fail loudly instead:
  https://code.claude.com/docs/en/sub-agents
"""
import re
import sys
from pathlib import Path

AGENTS_DIR = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else Path(__file__).resolve().parent.parent / "agents"
)
# Repo mode (no argument) also enforces this repo's own conventions. Pointed
# at an external agents directory, only the rules Claude Code itself applies
# are checked, since externals may validly use non-plugin fields and their
# own naming and formatting conventions.
REPO_MODE = len(sys.argv) <= 1

# Tool names valid in `tools` as of v2.1.288. Subagents may also reference
# MCP patterns (mcp__server, mcp__server__*), allowed by regex below.
KNOWN_TOOLS = {
    "Read", "Grep", "Glob", "LSP", "Bash", "PowerShell", "Edit", "Write",
    "NotebookEdit", "WebFetch", "WebSearch", "TodoWrite", "Skill",
    "ToolSearch", "EnterWorktree", "ExitWorktree", "Monitor", "TaskStop",
    "SendMessage", "Artifact", "Agent", "Task",
}
MCP_TOOL_RE = re.compile(r"^mcp__[A-Za-z0-9_-]+(__\*|__[A-Za-z0-9_-]+)?$")

MODEL_ALIASES = {"sonnet", "opus", "haiku", "fable", "inherit"}
EFFORT_LEVELS = {"low", "medium", "high", "xhigh", "max"}
COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}

# Fields a PLUGIN agent supports. permissionMode, hooks, mcpServers and
# initialPrompt are silently ignored when the agent ships in a plugin, so
# this repo bans them outright rather than shipping dead config.
PLUGIN_SUPPORTED_FIELDS = {
    "name", "description", "model", "effort", "maxTurns", "tools",
    "disallowedTools", "skills", "memory", "background", "omitClaudeMd",
    "isolation", "color", "experimental",
}

failures = []


def fail(path, msg):
    failures.append(f"{path.name}: {msg}")


def parse_frontmatter(text, path):
    """Minimal YAML frontmatter parser for the flat key: value subset we use."""
    lines = text.split("\n")
    if lines[0] != "---":
        fail(path, "frontmatter '---' must be on line 1 (Claude Code skips the file otherwise)")
        return None, ""
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        fail(path, "frontmatter never closes")
        return None, ""
    fm = {}
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")) or raw.lstrip().startswith("-"):
            if REPO_MODE:
                fail(path, f"nested/list frontmatter not allowed in this repo (keep it flat): {raw!r}")
            continue
        if ":" not in raw:
            fail(path, f"unparseable frontmatter line: {raw!r}")
            continue
        key, _, value = raw.partition(":")
        fm[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1:]).strip()
    return fm, body


def check_agent(path):
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text, path)
    if fm is None:
        return None

    # Unknown / plugin-ignored fields. Claude Code ignores unrecognized
    # fields without an error; we refuse them so typos cannot ship. Outside
    # a plugin, the four plugin-ignored fields are legitimate.
    allowed = PLUGIN_SUPPORTED_FIELDS if REPO_MODE else (
        PLUGIN_SUPPORTED_FIELDS | {"permissionMode", "hooks", "mcpServers", "initialPrompt"}
    )
    for key in fm:
        if key not in allowed:
            fail(path, f"field '{key}' is not a supported frontmatter field (typo or snake_case?)")

    name = fm.get("name", "")
    if not name:
        fail(path, "missing required field: name")
    else:
        if ":" in name or name.startswith("-"):
            fail(path, f"invalid name {name!r}: ':' is forbidden and a leading '-' makes Claude Code skip the file")
        if REPO_MODE and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            fail(path, f"name {name!r} should be lowercase kebab-case")
        if REPO_MODE and name != path.stem:
            fail(path, f"name {name!r} must match filename {path.stem!r} (repo convention)")

    desc = fm.get("description", "")
    if not desc:
        fail(path, "missing required field: description (Claude Code skips the file without it)")
    elif REPO_MODE and len(desc) > 350:
        fail(path, f"description is {len(desc)} chars; keep it under 350 so the combined description budget stays small")

    if "tools" in fm:
        tools = [t.strip() for t in fm["tools"].split(",") if t.strip()]
        if not tools:
            fail(path, "tools is present but empty: zero resolvable tools makes the subagent refuse to launch")
        for t in tools:
            if t not in KNOWN_TOOLS and not MCP_TOOL_RE.match(t):
                fail(path, f"unknown tool {t!r}")

    if "disallowedTools" in fm:
        for t in (x.strip() for x in fm["disallowedTools"].split(",")):
            if "(" in t:
                fail(path, f"disallowedTools entry {t!r} has a specifier; Claude Code removes the WHOLE tool, which is almost never what you meant")

    model = fm.get("model")
    if model and model not in MODEL_ALIASES and not model.startswith("claude-"):
        fail(path, f"model {model!r} is not an alias ({', '.join(sorted(MODEL_ALIASES))}) or a full claude-* model ID")

    effort = fm.get("effort")
    if effort and effort not in EFFORT_LEVELS:
        fail(path, f"effort {effort!r} not in {sorted(EFFORT_LEVELS)}")

    color = fm.get("color")
    if color and color not in COLORS:
        fail(path, f"color {color!r} not in {sorted(COLORS)}")

    if fm.get("isolation") not in (None, "worktree"):
        fail(path, "isolation only accepts 'worktree'")
    if fm.get("memory") not in (None, "user", "project", "local"):
        fail(path, "memory must be user, project, or local")

    # Body conventions: every agent states its job and its output contract.
    if not body:
        fail(path, "empty body: the body is the agent's system prompt")
    if REPO_MODE and "## Report format" not in body:
        fail(path, "missing '## Report format' section (repo convention: every agent has an explicit output contract)")
    if REPO_MODE and "\u2014" in text:
        fail(path, "contains an em dash; this repo's prose convention bans them")

    return fm


def main():
    agent_files = sorted(AGENTS_DIR.glob("*.md"))
    if not agent_files:
        print("FAIL: no agent files found", file=sys.stderr)
        return 1

    names = []
    descriptions = []
    for path in agent_files:
        fm = check_agent(path)
        if fm:
            names.append(fm.get("name", path.stem))
            descriptions.append(fm.get("description", ""))

    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        failures.append(f"duplicate agent names: {sorted(dupes)} (Claude Code loads only one, by filesystem read order)")

    # Claude Code warns when combined subagent descriptions pass 15,000
    # tokens. Rough proxy: 4 chars/token across all descriptions.
    approx_tokens = sum(len(d) for d in descriptions) // 4
    if REPO_MODE and approx_tokens > 2000:
        failures.append(f"combined descriptions approx {approx_tokens} tokens; this collection should stay far below the 15k budget")

    if failures:
        print(f"FAIL: {len(failures)} finding(s) across {len(agent_files)} agent file(s)\n", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: {len(agent_files)} agents, {len(names)} unique names, ~{approx_tokens} description tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
