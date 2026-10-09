param([Parameter(Mandatory=$true)][string]$PythonExecutable)
$ErrorActionPreference='Stop'
$server=Join-Path $PSScriptRoot 'companion_mcp.py'
if(!(Test-Path -LiteralPath $PythonExecutable -PathType Leaf)){throw 'Configured Python is missing. Regenerate the local plugin package.'}
if(!(Test-Path -LiteralPath $server -PathType Leaf)){throw 'The installed doll MCP server is missing.'}
# Keep stdout exclusively for the MCP protocol and let the SDK close stdin.
& $PythonExecutable $server
exit $LASTEXITCODE
