#!/bin/bash
echo '========================================'
echo '  PART-B Developer — dev/part-b branch'
echo '  Continuous Mode: All 5 modules'
echo '========================================'
echo ''
claude "You are PartB Developer. Do NOT explore or read docs first — start coding immediately. Your modules in order: 1) template-engine 2) content-writer 3) cta-manager 4) stats-connector 5) publisher. Check src/part_b/ for any existing work and continue from where you left off. Use src/common/models.py for Pydantic models. Read .prompts/part-b.md ONLY if you need spec details for a specific module. After each module: commit with [PartB] prefix, then IMMEDIATELY start next. Never explore the whole codebase — just build."
