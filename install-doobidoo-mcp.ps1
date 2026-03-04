<#
.SYNOPSIS
    Pre-installs the mcp-memory-service (doobidoo) package so the MCP server
    starts quickly without hitting Claude Code's startup timeout.

.DESCRIPTION
    Running `uvx --from mcp-memory-service memory server` for the first time
    downloads and installs the package, which can exceed Claude Code's MCP
    server startup timeout. This script pre-installs the package into the
    uv tool cache so subsequent launches are instant.

.NOTES
    Requires uv (https://docs.astral.sh/uv/) to be installed.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Check uv is available
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. Install it from https://docs.astral.sh/uv/"
    exit 1
}

Write-Host "Installing mcp-memory-service into uv tool cache..." -ForegroundColor Cyan
uv tool install mcp-memory-service

if ($LASTEXITCODE -ne 0) {
    Write-Host "uv tool install failed (exit code $LASTEXITCODE). Trying upgrade..." -ForegroundColor Yellow
    uv tool install --upgrade mcp-memory-service
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install mcp-memory-service."
        exit 1
    }
}

Write-Host ""
Write-Host "mcp-memory-service installed successfully." -ForegroundColor Green
Write-Host "The MCP server should now start without timeout issues." -ForegroundColor Green
