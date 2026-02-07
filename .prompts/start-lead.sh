#!/bin/bash
echo '========================================'
echo '  LEAD Developer — master branch'
echo '========================================'
echo ''
# Start Claude Code with the Lead role prompt
claude "$(cat "$(dirname "$0")/lead.md")"
