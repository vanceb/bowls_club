#!/usr/bin/env python3
"""
Test a single file to debug issues.
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

# Use the virtual environment python
python_path = '/home/vance/code/bowls_club/venv/bin/python'

# Test importing the models first
print("=== Testing Model Imports ===")
try:
    result = subprocess.run([python_path, '-c', 'from app.models import Member, Role, Booking; print("Model imports OK")'], 
                          capture_output=True, text=True, cwd='/home/vance/code/bowls_club')
    print("Model import output:", result.stdout)
    if result.stderr:
        print("Model import errors:", result.stderr)
    print("Model import return code:", result.returncode)
except Exception as e:
    print(f"Model import failed: {e}")

print("\n=== Testing Factory Imports ===")
try:
    result = subprocess.run([python_path, '-c', 'from tests.fixtures.factories import MemberFactory, BookingFactory; print("Factory imports OK")'], 
                          capture_output=True, text=True, cwd='/home/vance/code/bowls_club')
    print("Factory import output:", result.stdout)
    if result.stderr:
        print("Factory import errors:", result.stderr)
    print("Factory import return code:", result.returncode)
except Exception as e:
    print(f"Factory import failed: {e}")

print("\n=== Testing Single Test File ===")
try:
    result = subprocess.run([python_path, '-m', 'pytest', 'tests/unit/test_models.py', '-v'], 
                          capture_output=True, text=True, cwd='/home/vance/code/bowls_club', timeout=60)
    print("Single test output:", result.stdout)
    if result.stderr:
        print("Single test errors:", result.stderr)
    print("Single test return code:", result.returncode)
except subprocess.TimeoutExpired:
    print("Single test timed out")
except Exception as e:
    print(f"Single test failed: {e}")