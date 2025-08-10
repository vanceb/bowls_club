#!/usr/bin/env python3
"""
Test runner script for the Flask application.
Runs pytest with proper Flask configuration for testing.
"""
import os
import sys
import subprocess
import tempfile

def run_tests():
    """Run the complete test suite."""
    # Change to the project directory
    os.chdir('/home/vance/code/bowls_club')
    
    # Set critical environment variables for testing
    os.environ['FLASK_CONFIG'] = 'testing'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
    os.environ['MAIL_SUPPRESS_SEND'] = 'true'
    
    # Run a simple validation first - just try to import one test file
    print("=== Running Test Import Validation ===")
    try:
        import pytest
        # Try importing conftest to check basic setup
        from tests.conftest import app
        print("✓ Basic imports successful")
    except Exception as e:
        print(f"✗ Import validation failed: {e}")
        return False
    
    print("\n=== Running Full Test Suite ===")
    
    # Run pytest with basic configuration
    cmd = [
        sys.executable, '-m', 'pytest', 
        'tests/', 
        '-v', 
        '--tb=short',
        '--maxfail=5',  # Stop after 5 failures
        '-x'  # Stop on first failure
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        print(f"Return code: {result.returncode}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Tests timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)