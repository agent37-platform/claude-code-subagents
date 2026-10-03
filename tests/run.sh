#!/usr/bin/env bash
# Test suite: agent lint + manifest validation. Python 3 stdlib only.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== lint agents/"
python3 tests/lint-agents.py

echo "== validate plugin manifests are valid JSON"
python3 -m json.tool .claude-plugin/plugin.json > /dev/null
python3 -m json.tool .claude-plugin/marketplace.json > /dev/null

echo "== plugin name consistency"
python3 - <<'EOF'
import json, sys
plugin = json.load(open(".claude-plugin/plugin.json"))
market = json.load(open(".claude-plugin/marketplace.json"))
entry = market["plugins"][0]
assert plugin["name"] == entry["name"] == "subagents", "plugin name mismatch"
assert not plugin["name"].startswith(("claude-", "anthropic-")), "reserved plugin name prefix"
assert entry["source"] == "./", "marketplace source must be the repo root"
assert market["name"] == "agent37-subagents", "marketplace name drifted from the README install command"
print("OK: plugin.json and marketplace.json agree")
EOF

echo "All checks passed."
