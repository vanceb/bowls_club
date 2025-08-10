#!/usr/bin/env python3
"""
Minimal test runner to check for syntax and import errors.
"""
import os
import subprocess

os.chdir('/home/vance/code/bowls_club')
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-key'

python_path = '/home/vance/code/bowls_club/venv/bin/python'

# Try to run pytest on just one test file with maximum verbosity
cmd = [
    python_path, '-m', 'pytest', 
    'tests/unit/test_models.py',
    '-v', '--tb=long', '--no-header', '-x'
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print("Return code:", result.returncode)
    print("STDOUT:")
    print(result.stdout)
    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)
except subprocess.TimeoutExpired:
    print("Test timed out")
except Exception as e:
    print(f"Error: {e}")