#!/bin/bash
# TCO_Post_Engine — Agent Team Dev Launcher
# Launches 3 Windows Terminal panes with Claude Code auto-started per role.

PROJECT_ROOT="C:/Users/User/Desktop/project"
MAIN_DIR="$PROJECT_ROOT/TCO_Post_Engine"
PARTA_DIR="$PROJECT_ROOT/TCO_Post_Engine-partA"
PARTB_DIR="$PROJECT_ROOT/TCO_Post_Engine-partB"

PROMPTS_DIR="$MAIN_DIR/.prompts"

echo "=== TCO Post Engine — Agent Team Dev ==="
echo "Main (Lead):  $MAIN_DIR   [master]"
echo "PartA:        $PARTA_DIR  [dev/part-a]"
echo "PartB:        $PARTB_DIR  [dev/part-b]"
echo ""

# Verify worktrees exist
if [ ! -d "$PARTA_DIR" ] || [ ! -d "$PARTB_DIR" ]; then
    echo "ERROR: Worktrees not found. Run from main repo:"
    echo "  git worktree add ../TCO_Post_Engine-partA dev/part-a"
    echo "  git worktree add ../TCO_Post_Engine-partB dev/part-b"
    exit 1
fi

# Sync prompts to worktrees so each pane can read its own
cp -r "$PROMPTS_DIR" "$PARTA_DIR/.prompts" 2>/dev/null
cp -r "$PROMPTS_DIR" "$PARTB_DIR/.prompts" 2>/dev/null

# Make scripts executable
chmod +x "$PROMPTS_DIR"/start-*.sh
chmod +x "$PARTA_DIR/.prompts"/start-*.sh 2>/dev/null
chmod +x "$PARTB_DIR/.prompts"/start-*.sh 2>/dev/null

echo "Launching Windows Terminal with 3 agent panes..."
echo ""

# Launch Windows Terminal with 3 split panes
wt.exe \
  -d "$MAIN_DIR" --title "LEAD (main)" bash "$PROMPTS_DIR/start-lead.sh" \; \
  split-pane -H -d "$PARTA_DIR" --title "PART-A (dev/part-a)" bash "$PARTA_DIR/.prompts/start-part-a.sh" \; \
  split-pane -V -d "$PARTB_DIR" --title "PART-B (dev/part-b)" bash "$PARTB_DIR/.prompts/start-part-b.sh"

echo "Done. 3 Claude Code agents are now running in Windows Terminal."
