# 一键推送到 GitHub（需先 gh auth login 或配置 Git 凭据）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$git = "C:\Program Files\Git\bin\git.exe"
if (-not (Test-Path $git)) { $git = "git" }

& $git add -A
$status = & $git status --porcelain
if ($status) {
    & $git -c user.name="kydzhou" -c user.email="kydzhou@users.noreply.github.com" `
        commit -m "Update skland check-in project"
    Write-Host "已创建新提交"
} else {
    Write-Host "无文件变更，跳过 commit"
}

& $git push -u origin main
Write-Host "推送完成: https://github.com/kydzhou/skdcheckin"
