# 中文技能库 · 一键安装脚本（Windows PowerShell）
# 用法：.\install.ps1
$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot 'skills'
$target = if ($env:CLAUDE_SKILLS_DIR) { $env:CLAUDE_SKILLS_DIR } else { Join-Path $HOME '.claude\skills' }

Write-Host '中文技能库 · 安装脚本' -ForegroundColor Cyan
Write-Host "来源: $src"
Write-Host "目标: $target"

New-Item -ItemType Directory -Force -Path $target | Out-Null
$count = 0
Get-ChildItem -LiteralPath $src -Directory | ForEach-Object {
  Copy-Item -Recurse -Force $_.FullName (Join-Path $target $_.Name)
  $count++
}

Write-Host "已安装 $count 个技能到 $target" -ForegroundColor Green
Write-Host '下一步：在 Claude 里直接说"用 meeting-notes 技能帮我整理会议记录"即可开始使用。'
