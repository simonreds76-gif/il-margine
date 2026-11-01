"""Execute production PS helpers/guards without running the weekly main body."""
import subprocess, tempfile, unittest
from pathlib import Path

PS = 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
WEEKLY = Path(__file__).resolve().parents[1] / 'oncourt-weekly.ps1'

@unittest.skipUnless(Path(PS).exists(), 'Windows PowerShell required')
class WeeklyFreezeTests(unittest.TestCase):
    def run_ps(self, body):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / 'verify.ps1'
            script.write_text(r'''param($Source)
$ErrorActionPreference='Stop'
$tokens=$null; $parseErrors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw 'Parse error'}
''' + body, encoding='utf-8')
            p = subprocess.run([PS,'-NoProfile','-NonInteractive','-File',str(script),str(WEEKLY)], capture_output=True,text=True,timeout=20, creationflags=0x08000000)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_pending_manual_releases_outer_lock_before_next_weekly_operation(self):
        self.run_ps(r'''
foreach($name in @('Wait-WeeklyPriority','Invoke-WeeklyPython')){
 $fn=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
 Invoke-Expression $fn.Extent.Text
}
$script:order=New-Object System.Collections.Generic.List[string]
$root='mock-root'; $script:lockHandle='old'
function Get-TennisPriorityRequest { return @{request_id='manual'} }
function Exit-TaskLock($handle){if($handle -ne 'old'){throw 'Wrong handle'}; $script:order.Add('released')}
function Enter-TennisPriorityLock { $script:order.Add('manual completed then reacquired'); return 'new' }
function python {if($script:lockHandle -ne 'new'){throw 'No exclusive lock'}; $script:order.Add('python'); $global:LASTEXITCODE=17}
Invoke-WeeklyPython example.py
if($LASTEXITCODE -ne 17){throw 'Exit code lost'}
if(($script:order -join ',') -ne 'released,manual completed then reacquired,python'){throw 'Wrong ordering'}
''')

    def test_default_cannot_execute_handicap_refits(self):
        self.run_ps(r'''
$guard=$ast.Find({param($n) $n -is [System.Management.Automation.Language.IfStatementAst] -and $n.Clauses[0].Item1.Extent.Text -eq '$RefreshHistoricalResearch' -and $n.Extent.Text.Contains('handicap-calibration.py')},$true)
if($null -eq $guard){throw 'Refits have no explicit opt-in guard'}
$script:calls=0
function Invoke-LoggedProcess { $script:calls++; return 0 }
function Log {}
$RefreshHistoricalResearch=$false
Invoke-Expression $guard.Extent.Text
if($script:calls -ne 0){throw 'Default attempted refit'}
$RefreshHistoricalResearch=$true
$spreadFitFiles=@('fixture.csv'); $claySpreadFitFiles=@('fixture.csv')
function Test-Path { return $false }
Invoke-Expression $guard.Extent.Text
if($script:calls -ne 3){throw 'Explicit research path not preserved'}
''')

    def test_child_has_no_outer_lock_and_opts_into_cooperative_steps(self):
        self.run_ps(r'''
$text=$ast.Extent.Text
$start=$text.IndexOf('Exit-TaskLock $lockHandle', $text.IndexOf('# Step 9:'))
$end=$text.IndexOf('# Step 10:', $start)
$block=$text.Substring($start,$end-$start)
# Execute the actual handoff with mocked process/locks; no child launched.
function Log {}
$script:lockHandle='held'; $script:released=$false; $script:child=$false
function Exit-TaskLock { $script:released=$true }
function powershell {if(-not $script:released -or $null -ne $script:lockHandle){throw 'Outer lock blocks child'}; if('-CooperativeLock' -notin $args){throw 'Child not cooperative'}; $script:child=$true; $global:LASTEXITCODE=19}
function Enter-TennisPriorityLock {if(-not $script:child){throw 'Reacquired before child'}; return 'new'}
Invoke-Expression $block
if($LASTEXITCODE -ne 19 -or $lockHandle -ne 'new'){throw 'Handoff lost child status or lock'}
''')

if __name__ == '__main__': unittest.main()
