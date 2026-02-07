#!/bin/bash
echo '========================================'
echo '  PART-B Developer — dev/part-b branch'
echo '  Continuous Mode: All 5 modules'
echo '========================================'
echo ''
claude "You are the PartB Developer (Content Engine). Read .prompts/part-b.md for your FULL role instructions — especially the CRITICAL Continuous Operation Mode section. Then read dev_agent.md and CLAUDE.md. You must implement ALL 5 Part B modules continuously: template-engine, content-writer, cta-manager, stats-connector, publisher. If template-engine is already done, skip to content-writer. After each module: commit, update status, pull from main, then IMMEDIATELY start next module. NEVER stop between modules. Begin now on dev/part-b branch."
