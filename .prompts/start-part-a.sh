#!/bin/bash
echo '========================================'
echo '  PART-A Developer — dev/part-a branch'
echo '========================================'
echo ''
# Start Claude Code with the PartA role prompt
claude "$(cat "$(dirname "$0")/part-a.md")"
