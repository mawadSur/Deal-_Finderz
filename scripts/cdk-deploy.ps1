Param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

Write-Host "Checking Docker status..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "Docker CLI not found. Please install Docker Desktop and try again."; exit 1
}

docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Error "Docker does not appear to be running. Start Docker Desktop and retry."; exit 1
}

Write-Host "Docker is running. Deploying CDK..."
Push-Location cdk
try {
  cdk deploy @Args
} finally {
  Pop-Location
}
