import subprocess
import sys
import os

cmd = [r"C:\Users\User\AppData\Local\Programs\Python\Python311\python.exe", '-m', 'unittest', 'tests.test_sync_preserves_structure']
result = subprocess.run(cmd, cwd=os.path.abspath('.'), capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
print('exit_code', result.returncode)
