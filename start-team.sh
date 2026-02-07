#!/bin/bash
# TCO_Post_Engine — Agent Team Dev Launcher
# Launches 3 Windows Terminal panes: Lead / PartA / PartB
# Each pane runs Claude Code CLI targeting its respective worktree.

PROJECT_ROOT="C:/Users/User/Desktop/project"
MAIN_DIR="$PROJECT_ROOT/TCO_Post_Engine"
PARTA_DIR="$PROJECT_ROOT/TCO_Post_Engine-partA"
PARTB_DIR="$PROJECT_ROOT/TCO_Post_Engine-partB"

echo "=== TCO Post Engine — Agent Team Dev ==="
echo "Main (Lead):  $MAIN_DIR"
echo "PartA:        $PARTA_DIR"
echo "PartB:        $PARTB_DIR"
echo ""

# Verify worktrees exist
if [ ! -d "$PARTA_DIR" ] || [ ! -d "$PARTB_DIR" ]; then
    echo "ERROR: Worktrees not found. Run from main repo:"
    echo "  git worktree add ../TCO_Post_Engine-partA dev/part-a"
    echo "  git worktree add ../TCO_Post_Engine-partB dev/part-b"
    exit 1
fi

# Launch Windows Terminal with 3 split panes
wt.exe \
  -d "$MAIN_DIR" --title "LEAD (main)" bash -c "echo '=== LEAD Developer (main) ==='; echo 'Worktree: main'; echo ''; git log --oneline -3; echo ''; exec bash" \; \
  split-pane -H -d "$PARTA_DIR" --title "PART-A (dev/part-a)" bash -c "echo '=== PART-A Developer (dev/part-a) ==='; echo 'Worktree: dev/part-a'; echo ''; git log --oneline -3; echo ''; exec bash" \; \
  split-pane -V -d "$PARTB_DIR" --title "PART-B (dev/part-b)" bash -c "echo '=== PART-B Developer (dev/part-b) ==='; echo 'Worktree: dev/part-b'; echo ''; git log --oneline -3; echo ''; exec bash" \;

echo "Windows Terminal launched with 3 panes."
echo "Run 'claude' in each pane to start the respective developer agent."
