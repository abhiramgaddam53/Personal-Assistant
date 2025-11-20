#!/usr/bin/env python3
"""
Test script to verify basic functionality of the Personal Assistant
This tests the code without requiring actual API credentials
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        import config
        print("✓ config module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import config: {e}")
        return False
    
    try:
        import database
        print("✓ database module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import database: {e}")
        return False
    
    try:
        import utils
        print("✓ utils module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import utils: {e}")
        return False
    
    return True

def test_utils():
    """Test utility functions"""
    print("\nTesting utility functions...")
    from utils import validate_email, validate_user_id, validate_query
    
    # Test email validation
    assert validate_email("test@example.com") == True, "Valid email should pass"
    assert validate_email("invalid-email") == False, "Invalid email should fail"
    print("✓ Email validation works")
    
    # Test user ID validation
    try:
        validate_user_id("test_user")
        print("✓ User ID validation works")
    except ValueError:
        print("✗ User ID validation failed")
        return False
    
    # Test query validation
    try:
        result = validate_query("  test query  ")
        assert result == "test query", "Query should be trimmed"
        print("✓ Query validation works")
    except ValueError:
        print("✗ Query validation failed")
        return False
    
    return True

def test_config():
    """Test configuration"""
    print("\nTesting configuration...")
    try:
        from config import Config
        
        # Check that paths are created
        assert hasattr(Config, 'BASE_DIR'), "BASE_DIR should exist"
        assert hasattr(Config, 'DATA_DIR'), "DATA_DIR should exist"
        print(f"✓ Configuration loaded")
        print(f"  - BASE_DIR: {Config.BASE_DIR}")
        print(f"  - DATA_DIR: {Config.DATA_DIR}")
        
        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_rate_limiter():
    """Test rate limiter"""
    print("\nTesting rate limiter...")
    try:
        from utils import RateLimiter
        import time
        
        limiter = RateLimiter(max_calls=2, time_window=1)
        
        # First two calls should succeed
        assert limiter.is_allowed() == True, "First call should be allowed"
        assert limiter.is_allowed() == True, "Second call should be allowed"
        
        # Third call should fail
        assert limiter.is_allowed() == False, "Third call should be blocked"
        print("✓ Rate limiter works correctly")
        
        return True
    except Exception as e:
        print(f"✗ Rate limiter test failed: {e}")
        return False

def test_helper_functions():
    """Test helper functions"""
    print("\nTesting helper functions...")
    try:
        from utils import extract_email_from_text, extract_time_from_text, format_task_list
        
        # Test email extraction
        email = extract_email_from_text("Send email to test@example.com")
        assert email == "test@example.com", f"Expected test@example.com, got {email}"
        print("✓ Email extraction works")
        
        # Test time extraction
        time = extract_time_from_text("Meeting at 3:00 PM")
        assert time == "3:00 PM", f"Expected 3:00 PM, got {time}"
        print("✓ Time extraction works")
        
        # Test task formatting
        tasks = [
            {'description': 'Task 1', 'due_date': '2024-01-01', 'status': 'pending', 'priority': 'high'},
            {'description': 'Task 2', 'due_date': '2024-01-02', 'status': 'completed', 'priority': 'low'}
        ]
        formatted = format_task_list(tasks)
        assert 'Task 1' in formatted, "Task 1 should be in formatted output"
        assert 'Task 2' in formatted, "Task 2 should be in formatted output"
        print("✓ Task formatting works")
        
        return True
    except Exception as e:
        print(f"✗ Helper functions test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Personal Assistant - Code Verification Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config,
        test_utils,
        test_rate_limiter,
        test_helper_functions
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All tests passed! Code is working correctly.")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
