#!/usr/bin/env python3
"""
Run a single test file to debug issues.
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

print("=== Testing Model Import ===")
try:
    result = subprocess.run([
        python_path, '-c', 
        'from app.models import Member, Role, Booking, Pool; print("Model imports successful")'
    ], capture_output=True, text=True, cwd='/home/vance/code/bowls_club')
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
except Exception as e:
    print(f"Model import test failed: {e}")

print("\n=== Testing Factory Import ===")
try:
    result = subprocess.run([
        python_path, '-c', 
        'from tests.fixtures.factories import MemberFactory, BookingFactory; print("Factory imports successful")'
    ], capture_output=True, text=True, cwd='/home/vance/code/bowls_club')
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
except Exception as e:
    print(f"Factory import test failed: {e}")

print("\n=== Running Simple Test ===")
try:
    result = subprocess.run([
        python_path, '-m', 'pytest', 'tests/unit/test_models.py', '-v', '-x'
    ], capture_output=True, text=True, cwd='/home/vance/code/bowls_club', timeout=60)
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
except subprocess.TimeoutExpired:
    print("Test timed out")
except Exception as e:
    print(f"Test failed: {e}")