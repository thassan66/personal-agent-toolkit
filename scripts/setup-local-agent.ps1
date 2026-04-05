param(
    [ValidateSet("balanced", "reasoning", "agentic")]
    [string]$Profile = "balanced",
    [string]$Model,
    [string]$Workspace = ".",
    [switch]$Pull
)

$profileModels = @{
    balanced = "qwen2.5-coder:14b"
    reasoning = "deepseek-r1:14b"
    agentic = "devstral:24b"
}

if (-not $Model) {
    $Model = $profileModels[$Profile]
}

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    throw "Ollama is not installed or not on PATH. Install it first from https://ollama.com/."
}

if ($Pull) {
    & $ollama.Source pull $Model
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to pull model $Model."
    }
}

$env:PERSONAL_AGENT_TOOLKIT_PROVIDER = "ollama"
$env:PERSONAL_AGENT_TOOLKIT_BASE_URL = "http://localhost:11434/v1"
$env:PERSONAL_AGENT_TOOLKIT_API_KEY = "dummy"
$env:PERSONAL_AGENT_TOOLKIT_MODEL = $Model

Write-Host "Local agent profile: $Profile"
Write-Host "Model: $Model"
Write-Host "Workspace: $Workspace"
Write-Host ""
Write-Host "Environment variables set for this PowerShell session."
Write-Host "Starting Personal Agent Toolkit against your local Ollama server..."
Write-Host ""

python -m personal_agent_toolkit --cwd $Workspace --provider ollama --model $Model
