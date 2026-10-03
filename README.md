# Claude Code Subagents

Eleven tested [subagents](https://code.claude.com/docs/en/sub-agents) for Claude Code, built like production code instead of persona prompts: every agent pins the least-privilege toolset it needs, defines exactly what it reports back, and shipped only after being validated with the official plugin validator and exercised in a real session. No "you are a world-class expert" filler, no 150-agent catalog where the same debugger ships five times under different names.

Verified against **Claude Code v2.1.288 (October 2026)**: the [lint suite](tests/run.sh) enforces the frontmatter rules the CLI actually applies (it silently skips malformed agent files, so this repo fails loudly instead), CI runs it on Ubuntu and macOS plus `claude plugin validate --strict`, and the transcript below is from a live session, not a mock.

## Quick start

**As a plugin** (one marketplace add, one install):

```bash
claude plugin marketplace add agent37-platform/claude-code-subagents
claude plugin install subagents@agent37-subagents
```

(In a running session, `/plugin marketplace add` works the same; `/plugin install` opens the plugin panel where you confirm the install.)

Plugin agents are name-scoped: invoke as `subagents:code-reviewer`, or in a prompt via `@agent-subagents:code-reviewer`.

**Or copy into one project** (bare names; project files outrank plugin agents when names collide):

```bash
git clone https://github.com/agent37-platform/claude-code-subagents.git
mkdir -p your-project/.claude/agents
cp claude-code-subagents/agents/*.md your-project/.claude/agents/
```

Copy to `~/.claude/agents/` instead to get them in every project. Both directories hot-reload: edits and new files apply on the next delegation, no restart, with one catch: the watcher only covers agents directories that existed when the session started, so the first time you create `.claude/agents/` itself, restart the session.

**Or try once without installing anything**:

```bash
claude --plugin-dir ./claude-code-subagents
```

## The agents

| Agent | Tools | What it reports back |
|---|---|---|
| [`code-reviewer`](agents/code-reviewer.md) | read-only | severity-ranked correctness bugs in the current diff, each with file:line and a concrete failure scenario |
| [`security-auditor`](agents/security-auditor.md) | read-only, `effort: high` | exploitable vulnerabilities with the attack written out: who sends what, gains what |
| [`test-writer`](agents/test-writer.md) | +Edit, Write | tests in your repo's idiom, each proven to FAIL without your change and pass with it |
| [`debugger`](agents/debugger.md) | +Edit | root cause with the evidence that confirmed it, plus the minimal fix, instrumentation removed |
| [`flaky-test-hunter`](agents/flaky-test-hunter.md) | +Edit | the flake class (shared state, time, race, randomness), failure rate before and after the fix |
| [`git-archaeologist`](agents/git-archaeologist.md) | read-only | why the code is the way it is, every conclusion labeled documented / inferred / unknown |
| [`doc-syncer`](agents/doc-syncer.md) | +Edit | documentation drift found and fixed: stale claims, broken examples, wrong defaults |
| [`pr-writer`](agents/pr-writer.md) | read-only | a ready-to-paste PR title and body from the real commits and diff, in your repo's template |
| [`dependency-auditor`](agents/dependency-auditor.md) | +WebFetch, WebSearch | per-package ADOPT / ADOPT WITH PIN / REJECT verdicts with advisories, licenses, install scripts checked |
| [`claude-md-writer`](agents/claude-md-writer.md) | +Edit, Write | a CLAUDE.md where every documented command was actually run before being written down |
| [`migration-reviewer`](agents/migration-reviewer.md) | read-only, `effort: high` | lock hazards, data-loss traps, and deploy-order violations in schema migrations, plus the safe rollout order |

Read-only means `Read, Grep, Glob, Bash`: reviewers that cannot edit your files are reviewers you can run without watching them.

## One of them, live

A real headless v2.1.288 session against a diff with two planted bugs (`claude -p --plugin-dir . --model sonnet`), output verbatim:

```
> Use the subagents:code-reviewer subagent to review the current diff,
  then relay its full report verbatim

- [P1] stats.py:12 - The slice `values[max(0, i - window):i]` excludes the
  current element, and at i=0 it is empty. Failure: `moving_average([1,2,3], 2)`
  hits `sum([]) / 0` at i=0 and raises ZeroDivisionError. Any non-empty input
  fails. The slice should end at `i + 1`.
- [P2] stats.py:19 - With k=0, `[-0:]` is `[0:]`, so it returns every score
  instead of an empty list. Failure: `top_k([1,2,3], 0)` returns `[1,2,3]`.
- [P3] stats.py:12 - A window of 0 or less gives an empty or odd slice.
  Failure: `window=0` gives an empty chunk and a ZeroDivisionError. This is
  only worth guarding after the P1 fix.

Reviewed stats.py: 1 P1, 1 P2, 1 P3.
```

Both planted bugs found with the failing inputs spelled out, one real extra, zero invented findings, and the exact report format the agent's contract specifies. That contract adherence is the point: you can pipe this output somewhere and parse it.

## How these are built

Five rules, applied to every agent in [`agents/`](agents/):

1. **One job, stated in the first sentence.** Scope creep is the top subagent failure; every prompt says what the agent does not do.
2. **Least-privilege tools.** A code reviewer with Edit access will eventually "helpfully" fix something mid-review. The `tools` field is an allowlist; reviewers here cannot write.
3. **An explicit output contract.** The main conversation only ever sees the subagent's final report, so every agent has a `## Report format` section defining exactly what comes back.
4. **Evidence discipline over enthusiasm.** Findings need file:line and a failure scenario; claims need quotes; "looks fine" is not a verdict. Agents are told to drop what they cannot prove.
5. **Current syntax, linted.** Frontmatter fields are camelCase and Claude Code ignores unrecognized ones without any error, so [`tests/lint-agents.py`](tests/lint-agents.py) rejects typos, snake_case, unknown tools, invalid models, and the fields plugins silently ignore.

## Using subagents well

- **Automatic delegation** is driven by the `description` field plus your request. These descriptions say when to use each agent; phrases like "use proactively" make Claude delegate without being asked.
- **Guarantee a run** with an @-mention: `@agent-subagents:security-auditor check the auth changes` (or bare `@agent-security-auditor` if you copied the files).
- **Run a whole session as one agent**: `claude --agent code-reviewer` (copied files), or set `"agent"` in settings.
- **Background by default**: in interactive sessions subagents run in the background while you keep working; monitor with `/tasks`, background a foreground task with Ctrl+B. Sessions cap at 20 concurrent subagents.
- **Resume instead of respawn**: a finished subagent returns an agent ID; Claude can follow up via `SendMessage` with its context intact.
- **Headless**: `claude -p --agents ./agents.json "Review my changes"` takes JSON definitions; `claude --bg --agent <name> "task"` dispatches a background session.

## Frontmatter that actually exists in 2026

Most collections and tutorials still show only `name`/`description`/`tools`/`model`. Current Claude Code supports much more, and this repo's agents use what earns its place:

| Field | What it does |
|---|---|
| `name`, `description` | the only two required fields; `description` drives automatic delegation |
| `tools` / `disallowedTools` | allowlist / denylist; omit `tools` to inherit everything |
| `model` | `sonnet`, `opus`, `haiku`, `fable`, a full model ID, or `inherit` (the parent's model) |
| `effort` | reasoning effort: `low` to `max`; this repo sets `high` on the security and migration reviewers |
| `color` | tags the agent in the UI: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan` |
| `maxTurns` | hard turn cap; output past it is marked partial and resumable |
| `memory` | `user` / `project` / `local`: persistent cross-session memory directory for the agent |
| `background: true` | keeps the agent in the background even when asked to run foreground |
| `isolation: worktree` | runs the agent in a temporary git worktree |
| `skills` | preloads full skill content at startup |
| `omitClaudeMd` | skips user/project CLAUDE.md in the agent's context |

Gotchas that cost people hours, all verified against the [official docs](https://code.claude.com/docs/en/sub-agents) and v2.1.288:

- **Malformed files are skipped silently.** No `description`, frontmatter `---` not on line 1, a `:` in the name, or broken YAML, and the agent just never appears. The official validator only partially helps: on v2.1.288, `claude plugin validate <agents-dir>` flags YAML that fails to parse and warns on a missing description (exit 0 unless `--strict`), but passes a late `---` or a `:` in the name without a word. This repo's [`tests/lint-agents.py`](tests/lint-agents.py) rejects all four; point it at any agents directory (`python3 tests/lint-agents.py ~/.claude/agents`).
- **Fields are camelCase and typos fail silently.** `disallowed_tools` is ignored without a warning. Our lint rejects anything not in the supported set.
- **A `disallowedTools` specifier removes the whole tool.** `Bash(git push *)` does not block only pushes; it removes Bash entirely.
- **Plugins ignore four fields.** `permissionMode`, `hooks`, `mcpServers`, and `initialPrompt` do nothing in a plugin-shipped agent; ship those as plugin-level components instead. This repo's agents only use plugin-safe fields.
- **`isolation: worktree` branches from your default branch**, not the session's HEAD, so diff-reviewing agents (most of this repo) must not use it: the uncommitted change they review would not exist in the worktree.
- **Model aliases resolve within the parent's family.** With the main session on an Opus-family model, `model: opus` in an agent resolves to the parent's exact model, extended-context suffix included.
- **Descriptions share a budget.** Claude Code warns when combined subagent descriptions pass 15,000 tokens; 161-agent catalogs eat real context. These eleven total about 560 tokens.
- **`/agents` is vestigial** since v2.1.198: it prints a pointer. Manage files directly, monitor in `/tasks`, and note `claude agents` (the CLI command) is a different feature for parallel background sessions.

## Tested, actually

```bash
bash tests/run.sh                            # stdlib-only lint of every agent + manifests
claude plugin validate agents --strict       # the official validator on the agent files
claude plugin validate . --strict            # and on the marketplace manifest
```

Two validator runs because of a subtlety worth knowing: pointed at a directory containing `.claude-plugin/marketplace.json`, the official validator checks the marketplace manifest and never opens the agent files; you have to aim it at the `agents/` directory separately. The lint enforces what the CLI silently requires (frontmatter on line 1, valid names, known tools, plugin-safe fields, unique names) plus this repo's conventions (filename = agent name, an explicit `## Report format` in every agent, descriptions under 350 chars). CI runs all of it on every pull request and every push to main. The session transcript above was produced with this exact repo via `--plugin-dir`.

## Honest limits

Subagents are not free: each one starts with a clean context, so it re-reads the code you were just looking at, and tokens spent in a subagent are real spend. Delegation is also only as good as the `description` field; a vague description means the agent never fires automatically. And a prompt is still a prompt: these agents make good behavior much more likely, they do not make bad behavior impossible. For deterministic guarantees (blocking force-pushes, protecting secrets), pair them with [hooks](https://github.com/agent37-platform/claude-code-hooks).

## Run it always-on

Subagents shine in sessions nobody is watching: a nightly code-review sweep, a scheduled dependency audit, a doc-sync pass after every merge. [Agent37](https://www.agent37.com/solutions/claude-code-hosting?utm_source=github&utm_repo=claude-code-subagents) runs Claude Code as an always-on cloud instance on your own Anthropic account, from $4.76/mo (2 vCPU / 4 GB RAM / 4 GB disk), metered per minute with a $5 starter credit once a card is on file. Drop these agents into the instance's `~/.claude/agents/` and every scheduled run gets the same reviewers.

## Related

- [claude-code-hooks](https://github.com/agent37-platform/claude-code-hooks): deterministic guardrails these agents complement; same team, same testing bar
- [claude-code-docker](https://github.com/agent37-platform/claude-code-docker): pinned, egress-firewalled image for running Claude Code (and these agents) in a container
- [Official subagents docs](https://code.claude.com/docs/en/sub-agents): the reference this repo is linted against
- [wshobson/agents](https://github.com/wshobson/agents) and [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents): the big catalogs, if you want 150+ agents to pick through

## License

MIT
