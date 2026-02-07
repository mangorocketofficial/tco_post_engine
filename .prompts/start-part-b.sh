#!/bin/bash
echo '========================================'
echo '  PART-B Developer — dev/part-b branch'
echo '========================================'
echo ''
# Start Claude Code with the PartB role prompt
claude "$(cat "$(dirname "$0")/part-b.md")"
