#!/bin/bash
echo '========================================'
echo '  LEAD Developer — master branch'
echo '  Continuous Mode: Phase 1 Weeks 1-3'
echo '========================================'
echo ''
claude "You are Lead Developer. Do NOT explore extensively — act immediately. Check .coordination/status-partA.md and status-partB.md for developer progress. If a branch has new commits: merge it to main with git merge, run pytest tests/, fix any conflicts. Then update .coordination/status.md with next directives. Repeat this check-merge-test-direct cycle until Phase 1 is complete. Read .prompts/lead.md ONLY if you need timeline details. Commit with [Lead] prefix."
