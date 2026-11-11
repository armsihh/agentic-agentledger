# Overnight best-effort run: B0 (E1), B1 all_at_once (E2), and our system (E3) against as much
# of the full 184-log real Who&When benchmark as the day's free-tier quota allows. Each of the
# three eval scripts already treats a per-run failure as "skip and continue" (see run_baseline.py
# / run_b1.py / run_system.py), so pointing them at the full 184 with no --limit naturally yields
# "as many as possible" rather than requiring an all-or-nothing run: once quota is truly
# exhausted everywhere, remaining runs fail fast (see GroqProvider/OpenRouterProvider's
# "tokens per day" fast-fail) instead of hanging, so the script still finishes in bounded time.
#
# Triggered by a one-time Windows Scheduled Task (see docs/devlog.md for how/why); can also be
# run by hand: powershell -File scripts/run_overnight_full.ps1

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$EnvFile = Join-Path $ProjectRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $name = $Matches[1]
            $value = $Matches[2]
            if ($value -ne "") {
                [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = Join-Path $ProjectRoot "logs_overnight"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "overnight_full_$Timestamp.log"
$RealRoot = "../reference-Agents_Failure_Attribution/Who&When"

function Run-Step($Name, $ScriptArgs) {
    # NOTE: the parameter was originally named $Args, which collides with PowerShell's reserved
    # automatic $args variable (unbound extra arguments) -- that collision made `python -u @Args`
    # expand to nothing, so `python` launched its own interactive REPL instead of the eval
    # script, which then crashed on readline/stdin under a non-interactive background process.
    # Found by inspecting the log from a run that was stopped seconds after starting, before any
    # quota was spent. Renamed to $ScriptArgs to avoid the collision entirely.
    Add-Content $LogFile "`n===== $(Get-Date -Format o) START $Name =====`n"
    try {
        & python -u @ScriptArgs 2>&1 | Tee-Object -FilePath $LogFile -Append
    } catch {
        Add-Content $LogFile "`n$Name crashed at the PowerShell level: $_`n"
    }
    Add-Content $LogFile "`n===== $(Get-Date -Format o) END $Name =====`n"
}

Run-Step "E1 (B0, full real benchmark)" @(
    "eval/run_baseline.py", "--real-whowhen-root", $RealRoot,
    "--out", "results/baseline_b0_real_full184.json"
)

Run-Step "E2 (B1 all_at_once, full real benchmark)" @(
    "eval/run_b1.py", "--real-whowhen-root", $RealRoot, "--method", "all_at_once",
    "--out", "results/baseline_b1_real_full184_allatonce.json"
)

Run-Step "E3 (our system, full real benchmark)" @(
    "eval/run_system.py", "--real-whowhen-root", $RealRoot,
    "--out", "results/system_results_full184.json",
    "--trajectory-dir", "logs_full184"
)

Add-Content $LogFile "`n===== $(Get-Date -Format o) ALL STEPS DONE =====`n"
