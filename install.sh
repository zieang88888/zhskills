#!/usr/bin/env bash
# 中文技能库 · 一键安装脚本（macOS / Linux）
# 用法：./install.sh
set -euo pipefail

SKILLS_SRC="$(cd "$(dirname "$0")" && pwd)/skills"
TARGET="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

echo "中文技能库 · 安装脚本"
echo "来源：$SKILLS_SRC"
echo "目标：$TARGET"

mkdir -p "$TARGET"
count=0
for skill in "$SKILLS_SRC"/*/; do
  [ -d "$skill" ] || continue
  name="$(basename "$skill")"
  cp -R "$skill" "$TARGET/$name"
  count=$((count + 1))
done

echo "已安装 $count 个技能到 $TARGET"
echo "下一步：在 Claude 里直接说『用 meeting-notes 技能帮我整理会议记录』即可开始使用。"
