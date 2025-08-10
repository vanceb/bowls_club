#!/usr/bin/env python3
"""
Comprehensive test runner that captures detailed results.
"""
import os
import sys
import subprocess
import time

# Change to project directory
os.chdir('/home/vance/code/bowls_club')

# Set environment for testing
os.environ['FLASK_CONFIG'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-testing'
os.environ['MAIL_SUPPRESS_SEND'] = 'true'

# Use the virtual environment python
python_path = '/home/vance/code/bowls_club/venv/bin/python'

def run_test_category(category_name, test_path, max_failures=None):
    """Run tests in a specific category and return results."""
    print(f"\n{'='*60}")
    print(f"Running {category_name}")
    print(f"{'='*60}")
    
    cmd = [python_path, '-m', 'pytest', test_path, '-v', '--tb=short']
    if max_failures:
        cmd.extend(['--maxfail', str(max_failures)])
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, 
                              cwd='/home/vance/code/bowls_club', timeout=300)
        end_time = time.time()
        
        print(f"Duration: {end_time - start_time:.2f} seconds")
        print(f"Return code: {result.returncode}")
        
        if result.stdout:
            print("\nSTDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
            
        return {
            'category': category_name,
            'return_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': end_time - start_time
        }
        
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {category_name} tests timed out after 5 minutes")
        return {
            'category': category_name,
            'return_code': 'TIMEOUT',
            'stdout': '',
            'stderr': 'Test timed out',
            'duration': 300
        }
    except Exception as e:
        print(f"ERROR: Failed to run {category_name}: {e}")
        return {
            'category': category_name,
            'return_code': 'ERROR',
            'stdout': '',
            'stderr': str(e),
            'duration': 0
        }

def main():
    """Run comprehensive test suite."""
    print("COMPREHENSIVE TEST SUITE RUNNER")
    print("="*60)
    print(f"Working directory: {os.getcwd()}")
    print(f"Python path: {python_path}")
    print(f"Environment: {os.environ.get('FLASK_CONFIG', 'not set')}")
    
    # Test categories to run
    test_categories = [
        ("Unit Tests", "tests/unit/"),
        ("Integration Tests", "tests/integration/"),
        ("Functional Tests", "tests/functional/"),
        ("All Tests", "tests/"),
    ]
    
    results = []
    
    # Run each category
    for category_name, test_path in test_categories:
        if category_name == "All Tests":
            # Skip if we already ran individual categories
            continue
            
        result = run_test_category(category_name, test_path, max_failures=10)
        results.append(result)
    
    # Generate summary report
    print(f"\n{'='*60}")
    print("COMPREHENSIVE TEST REPORT SUMMARY")
    print(f"{'='*60}")
    
    total_duration = sum(r['duration'] for r in results if isinstance(r['duration'], (int, float)))
    print(f"Total test duration: {total_duration:.2f} seconds")
    
    for result in results:
        status = "PASSED" if result['return_code'] == 0 else "FAILED"
        print(f"{result['category']:<20} {status:<10} Duration: {result['duration']:.2f}s")
        
        # Try to extract test counts from pytest output
        stdout = result['stdout']
        if 'failed' in stdout or 'passed' in stdout:
            # Look for pytest summary line
            lines = stdout.split('\n')
            for line in lines:
                if ('failed' in line or 'passed' in line) and ('warning' in line or 'error' in line or '==' in line):
                    print(f"  └─ {line.strip()}")
                    break
    
    # Analyze failures
    print(f"\n{'='*60}")
    print("FAILURE ANALYSIS")
    print(f"{'='*60}")
    
    for result in results:
        if result['return_code'] != 0:
            print(f"\n{result['category']} FAILURES:")
            
            # Extract error information from stderr and stdout
            stderr = result['stderr']
            stdout = result['stdout']
            
            if stderr:
                print(f"Error output: {stderr[:500]}...")
            
            if 'FAILED' in stdout:
                # Extract failed test names
                lines = stdout.split('\n')
                failed_tests = [line for line in lines if 'FAILED' in line]
                for test in failed_tests[:5]:  # Show first 5 failures
                    print(f"  - {test}")
                if len(failed_tests) > 5:
                    print(f"  ... and {len(failed_tests) - 5} more failures")
    
    print(f"\n{'='*60}")
    print("END OF COMPREHENSIVE TEST REPORT")
    print(f"{'='*60}")
    
    # Return overall success/failure
    failed_categories = [r for r in results if r['return_code'] != 0]
    return len(failed_categories) == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)