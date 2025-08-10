#!/usr/bin/env python3
"""
Simple test analysis script to run tests and capture results.
"""
import os
import sys
import subprocess

# Change to project directory
os.chdir('/home/vance/code/bowls_club')

# Set environment for testing
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

# Activate virtual environment by using the python from venv
python_path = '/home/vance/code/bowls_club/venv/bin/python'

# Try import validation first
print("=== Import Validation ===")
try:
    result = subprocess.run([python_path, '-c', 'import pytest; from tests.conftest import app; print("Imports OK")'], 
                          capture_output=True, text=True, cwd='/home/vance/code/bowls_club')
    print("Import test output:", result.stdout)
    if result.stderr:
        print("Import test errors:", result.stderr)
    print("Import test return code:", result.returncode)
except Exception as e:
    print(f"Import test failed: {e}")

print("\n=== Running Test Discovery ===")
try:
    result = subprocess.run([python_path, '-m', 'pytest', 'tests/', '--collect-only', '-q'], 
                          capture_output=True, text=True, cwd='/home/vance/code/bowls_club')
    print("Collection output:", result.stdout)
    if result.stderr:
        print("Collection errors:", result.stderr)
    print("Collection return code:", result.returncode)
except Exception as e:
    print(f"Test collection failed: {e}")

print("\n=== Running Tests ===")
try:
    result = subprocess.run([python_path, '-m', 'pytest', 'tests/', '-v', '--tb=short', '--maxfail=3'], 
                          capture_output=True, text=True, cwd='/home/vance/code/bowls_club', timeout=300)
    print("Test output:", result.stdout)
    if result.stderr:
        print("Test errors:", result.stderr)
    print("Test return code:", result.returncode)
except subprocess.TimeoutExpired:
    print("Tests timed out")
except Exception as e:
    print(f"Test execution failed: {e}")