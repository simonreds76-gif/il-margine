import json, os, subprocess, tempfile, time, unittest
from pathlib import Path
PS='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
HELPER=Path(__file__).resolve().parents[1]/'tennis-priority.ps1'
class PriorityLockTests(unittest.TestCase):
 def test_manual_runs_before_next_history_step_without_overlapping_writer(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder); (root/'data/locks').mkdir(parents=True)
   script=root/'worker.ps1'
   script.write_text('''param($RootPath,$Helper,$Role)
. $Helper
if($Role -eq 'current') { $h=Enter-TennisPriorityLock $RootPath; Set-Content "$RootPath/current-entered" 'yes'; while(-not(Test-Path "$RootPath/release-current")){Start-Sleep -Milliseconds 50} }
else { $h=Enter-TennisPriorityLock -RootPath $RootPath -Priority:($Role -eq 'manual') -WaitSeconds 15 -PollSeconds 0; Set-Content "$RootPath/$Role-entered" 'yes'; if($Role -eq 'manual'){Start-Sleep -Milliseconds 250} }
Exit-TaskLock $h
if($Role -eq 'manual'){Remove-Item -LiteralPath "$RootPath/data/locks/tennis-on-demand-request.json"}
''',encoding='utf-8')
   def launch(role):
    return subprocess.Popen([PS,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(root),str(HELPER),role],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   def wait_file(name):
    limit=time.monotonic()+12
    while not(root/name).exists():
     if time.monotonic()>limit:self.fail('Missing '+name)
     time.sleep(.05)
   current=launch('current');wait_file('current-entered')
   (root/'data/locks/tennis-on-demand-request.json').write_text(json.dumps({'request_id':'test','expires_at':'2099-01-01T00:00:00Z'}))
   history=launch('history'); manual=launch('manual');time.sleep(.4)
   self.assertFalse((root/'manual-entered').exists());self.assertFalse((root/'history-entered').exists())
   (root/'release-current').touch();wait_file('manual-entered')
   self.assertFalse((root/'history-entered').exists());wait_file('history-entered')
   for process in [current,history,manual]:
    out,err=process.communicate(timeout=15);self.assertEqual(process.returncode,0,err.decode(errors='replace'))
 def test_python_exit_code_survives_wrapper_and_lock_is_released(self):
  with tempfile.TemporaryDirectory() as folder:
   script=Path(folder)/'exit.ps1'
   script.write_text('''param($root,$helper)
. $helper
function python { $global:LASTEXITCODE=17 }
Invoke-TennisHistoryPython example.py
if($LASTEXITCODE -ne 17){throw "Exit code lost: $LASTEXITCODE"}
$lock=Enter-TaskLock -LockName 'tennis-automation' -RootPath $root
if($null -eq $lock){throw 'Lock leaked'}
Exit-TaskLock $lock
''')
   result=subprocess.run([PS,'-NoProfile','-File',str(script),folder,str(HELPER)],capture_output=True,text=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   self.assertEqual(result.returncode,0,result.stderr)
if __name__=='__main__': unittest.main()
