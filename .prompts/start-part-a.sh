#!/bin/bash
echo '========================================'
echo '  PART-A Developer — dev/part-a branch'
echo '  Continuous Mode: All 5 modules'
echo '========================================'
echo ''
claude "You are the PartA Developer (Data Engine). Read .prompts/part-a.md for your FULL role instructions — especially the CRITICAL Continuous Operation Mode section. Then read dev_agent.md and CLAUDE.md. You must implement ALL 5 Part A modules continuously: price-tracker, resale-tracker, repair-analyzer, maintenance-calc, tco-engine. After each module: commit, update status, pull from main, then IMMEDIATELY start next module. NEVER stop between modules. Begin now on dev/part-a branch."
