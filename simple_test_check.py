#!/usr/bin/env python3
"""
Simple test check to see current status.
"""
import os
import sys
import subprocess

# Set up environment
os.chdir('/home/vance/code/bowls_club')
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

python_path = '/home/vance/code/bowls_club/venv/bin/python'

print("=== Quick Test Check ===")

# 1. Test basic imports
print("1. Testing basic imports...")
try:
    result = subprocess.run([
        python_path, '-c',
        '''
import sys
sys.path.insert(0, "/home/vance/code/bowls_club")
from app import create_app
from app.models import Booking, Pool, Member
from tests.fixtures.factories import BookingFactory, MemberFactory
print("✓ All imports successful")
'''
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("   ✓ Basic imports work")
    else:
        print(f"   ✗ Import failed: {result.stderr}")
        print(f"   stdout: {result.stdout}")
except Exception as e:
    print(f"   ✗ Exception: {e}")

# 2. Test collection (see if pytest can find and collect tests)
print("\n2. Testing test collection...")
try:
    result = subprocess.run([
        python_path, '-m', 'pytest', 'tests/', '--collect-only', '-q'
    ], capture_output=True, text=True, timeout=30)
    
    if result.returncode == 0:
        lines = result.stdout.split('\n')
        test_count = len([line for line in lines if '::test_' in line])
        print(f"   ✓ Test collection successful: found ~{test_count} tests")
    else:
        print(f"   ✗ Collection failed (code {result.returncode})")
        if result.stderr:
            print(f"   stderr: {result.stderr[:200]}...")
        if result.stdout:
            print(f"   stdout: {result.stdout[:200]}...")

except Exception as e:
    print(f"   ✗ Exception: {e}")

# 3. Try to run one simple test
print("\n3. Testing one simple test file...")
try:
    result = subprocess.run([
        python_path, '-m', 'pytest', 'tests/unit/', '-v', '--tb=short', '--maxfail=3'
    ], capture_output=True, text=True, timeout=60)
    
    print(f"   Return code: {result.returncode}")
    
    # Look for pass/fail counts
    stdout = result.stdout
    if 'passed' in stdout or 'failed' in stdout:
        lines = stdout.split('\n')
        summary_lines = [line for line in lines if ('passed' in line or 'failed' in line) and ('==' in line or 'warning' in line)]
        for line in summary_lines:
            print(f"   {line}")
    
    # Show any immediate failures
    if result.stderr:
        print(f"   stderr: {result.stderr[:300]}...")

except Exception as e:
    print(f"   ✗ Exception: {e}")

print("\n=== End Quick Check ===")