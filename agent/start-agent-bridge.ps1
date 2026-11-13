param(
  [int]$Port = 8765,
  [ValidateSet("auto", "edge", "chrome")]
  [string]$Browser = "auto",
  [string]$Token = "",
  [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bridge = Join-Path $scriptDir "xy_plotter_bridge.py"

$bridgeArgs = @(
  $bridge,
  "--port", [string]$Port,
  "--browser", $Browser
)

if ($Token) {
  $bridgeArgs += @("--token", $Token)
}
if ($NoOpen) {
  $bridgeArgs += "--no-open"
}

if (Get-Command py -ErrorAction SilentlyContinue) {
  & py @bridgeArgs
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  & python @bridgeArgs
} else {
  throw "Python 3 was not found. Install Python 3.10 or newer and retry."
}
