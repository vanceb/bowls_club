#!/usr/bin/env python3
"""
Run pool strategy tests specifically.
"""
import os
import sys
import subprocess

# Change to project directory
os.chdir('/home/vance/code/bowls_club')

# Set environment for testing
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

# Use the virtual environment python
python_path = '/home/vance/code/bowls_club/venv/bin/python'

print("=== Pool Strategy Test Suite ===")

print("\n1. Testing Pool Strategy Utils Import...")
try:
    result = subprocess.run([
        python_path, '-c', 
        '''
from app.bookings.utils import (
    get_pool_strategy_for_booking,
    get_primary_booking_in_series,
    should_create_pool_for_duplication,
    get_effective_pool_for_booking
)
print("✓ Pool strategy utils imports successful")
        '''
    ], capture_output=True, text=True, cwd='/home/vance/code/bowls_club')
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
except Exception as e:
    print(f"✗ Pool strategy utils import test failed: {e}")

print("\n2. Testing Booking Model Methods Import...")
try:
    result = subprocess.run([
        python_path, '-c', 
        '''
from app.models import Booking
from tests.fixtures.factories import BookingFactory
print("✓ Booking model and factory imports successful")
        '''
    ], capture_output=True, text=True, cwd='/home/vance/code/bowls_club')
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
except Exception as e:
    print(f"✗ Booking model import test failed: {e}")

print("\n3. Running Pool Strategy Unit Tests...")
try:
    result = subprocess.run([
        python_path, '-m', 'pytest', 
        'tests/unit/test_pool_strategy.py', 
        '-v', '--tb=short', '-x'
    ], capture_output=True, text=True, cwd='/home/vance/code/bowls_club', timeout=120)
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
    if result.returncode == 0:
        print("✅ Unit tests PASSED!")
    else:
        print("❌ Unit tests FAILED!")
except subprocess.TimeoutExpired:
    print("⏰ Unit tests timed out")
except Exception as e:
    print(f"✗ Unit test execution failed: {e}")

print("\n4. Running Pool Strategy Integration Tests...")
try:
    result = subprocess.run([
        python_path, '-m', 'pytest', 
        'tests/integration/test_booking_integration.py::TestPoolStrategyIntegration', 
        '-v', '--tb=short', '-x'
    ], capture_output=True, text=True, cwd='/home/vance/code/bowls_club', timeout=120)
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
    if result.returncode == 0:
        print("✅ Integration tests PASSED!")
    else:
        print("❌ Integration tests FAILED!")
except subprocess.TimeoutExpired:
    print("⏰ Integration tests timed out")
except Exception as e:
    print(f"✗ Integration test execution failed: {e}")

print("\n5. Running Basic Pool Strategy Functionality Test...")
try:
    result = subprocess.run([
        python_path, 'test_pool_strategy.py'
    ], capture_output=True, text=True, cwd='/home/vance/code/bowls_club', timeout=60)
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
    if result.returncode == 0:
        print("✅ Basic functionality test PASSED!")
    else:
        print("❌ Basic functionality test FAILED!")
except subprocess.TimeoutExpired:
    print("⏰ Basic functionality test timed out")
except Exception as e:
    print(f"✗ Basic functionality test failed: {e}")

print("\n=== Pool Strategy Test Suite Complete ===")