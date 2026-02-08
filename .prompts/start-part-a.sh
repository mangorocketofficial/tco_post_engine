#!/bin/bash
echo '========================================'
echo '  PART-A Developer — dev/part-a branch'
echo '  Continuous Mode: All 5 modules'
echo '========================================'
echo ''
claude "You are PartA Developer. Do NOT explore or read docs first — start coding immediately. Your modules in order: 1) price-tracker 2) resale-tracker 3) repair-analyzer 4) maintenance-calc 5) tco-engine. Check src/part_a/ for any existing work and continue from where you left off. Use src/common/models.py for Pydantic models and src/common/database.py for DB. Read .prompts/part-a.md ONLY if you need spec details for a specific module. After each module: commit with [PartA] prefix, then IMMEDIATELY start next. Never explore the whole codebase — just build."
