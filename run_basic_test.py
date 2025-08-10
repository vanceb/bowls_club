#!/usr/bin/env python3
"""
Basic test runner to validate setup and run one simple test.
"""
import os
import sys
import subprocess

def main():
    # Change to project directory
    os.chdir('/home/vance/code/bowls_club')
    
    # Set environment variables
    os.environ['FLASK_CONFIG'] = 'testing'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-testing-only'
    os.environ['MAIL_SUPPRESS_SEND'] = 'true'
    
    print("=== Running Basic Validation ===")
    
    # First run our validation script
    try:
        exec(open('validate_tests.py').read())
    except Exception as e:
        print(f"Validation failed: {e}")
        return False
    
    print("\n=== Running Simple Unit Tests ===")
    
    # Try to run unit tests only (they're simpler)
    cmd = [
        sys.executable, '-m', 'pytest', 
        'tests/unit/test_models.py',
        '-v',
        '--tb=short',
        '-x'  # Stop on first failure
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        print(f"Return code: {result.returncode}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Tests timed out")
        return False
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)