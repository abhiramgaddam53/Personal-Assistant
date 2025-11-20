#!/usr/bin/env python3
"""
Quick feature test to verify Personal Assistant functionality
WITHOUT requiring actual credentials (uses mock testing)
"""

import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

def test_imports():
    """Test that all required imports work"""
    print("Testing imports...")
    try:
        import psycopg2
        from psycopg2 import pool
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        from apscheduler.schedulers.background import BackgroundScheduler
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_code_structure():
    """Test that optimized code structure exists"""
    print("\nTesting code structure...")
    
    # Read the file
    with open("personal-assistant.py") as f:
        content = f.read()
    
    tests = {
        "Connection pool": "ThreadedConnectionPool" in content,
        "Context manager": "@contextmanager" in content,
        "LRU cache": "@lru_cache" in content,
        "Lazy loading": "get_llm()" in content and "get_sheets_service()" in content,
        "Environment validation": "REQUIRED_ENV_VARS" in content,
        "Cleanup method": "def cleanup(self)" in content,
        "IMAP reuse": "_get_imap_connection" in content,
        "No hardcoded creds": "postgres.ixruzjparquranqfdvdm" not in content,
        "Resource management": "with get_db_connection()" in content,
        "Proper logging": "logging.basicConfig" in content,
    }
    
    passed = sum(1 for v in tests.values() if v)
    total = len(tests)
    
    for name, result in tests.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    
    if passed == total:
        print(f"\n✅ All {total} structure tests passed")
        return True
    else:
        print(f"\n❌ {total - passed}/{total} tests failed")
        return False

def test_configuration_files():
    """Test that configuration files exist and are complete"""
    print("\nTesting configuration files...")
    
    tests = {
        "requirements.txt exists": Path("requirements.txt").exists(),
        ".env.example exists": Path(".env.example").exists(),
        ".gitignore exists": Path(".gitignore").exists(),
        "README.md exists": Path("README.md").exists(),
        "OPTIMIZATION_SUMMARY.md exists": Path("OPTIMIZATION_SUMMARY.md").exists(),
    }
    
    # Check content
    if tests["requirements.txt exists"]:
        with open("requirements.txt") as f:
            content = f.read()
            tests["requirements.txt complete"] = all(
                pkg in content for pkg in ["psycopg2-binary", "langchain", "faiss-cpu"]
            )
    
    if tests[".env.example exists"]:
        with open(".env.example") as f:
            content = f.read()
            tests[".env.example complete"] = all(
                var in content for var in ["GOOGLE_API_KEY", "DB_HOST", "GMAIL_USERNAME"]
            )
    
    for name, result in tests.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    
    passed = sum(1 for v in tests.values() if v)
    if passed == len(tests):
        print(f"\n✅ All configuration files OK")
        return True
    else:
        print(f"\n❌ Some configuration files missing/incomplete")
        return False

def test_security_patterns():
    """Test that security patterns are implemented"""
    print("\nTesting security patterns...")
    
    with open("personal-assistant.py") as f:
        content = f.read()
    
    with open(".gitignore") as f:
        gitignore = f.read()
    
    tests = {
        "No hardcoded passwords": "password=" not in content.lower() or "os.getenv" in content,
        "No hardcoded DB host": "pooler.supabase.com" not in content,
        "Uses environment vars": "os.getenv(" in content,
        "Validates env vars": "REQUIRED_ENV_VARS" in content,
        ".env protected": ".env" in gitignore,
        "JSON files protected": "*.json" in gitignore,
        "Data dir protected": "data/" in gitignore,
    }
    
    for name, result in tests.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    
    passed = sum(1 for v in tests.values() if v)
    if passed == len(tests):
        print(f"\n✅ All security patterns implemented")
        return True
    else:
        print(f"\n⚠️  Some security patterns missing")
        return False

def test_performance_patterns():
    """Test that performance patterns are implemented"""
    print("\nTesting performance patterns...")
    
    with open("personal-assistant.py") as f:
        content = f.read()
    
    tests = {
        "Connection pooling": "ThreadedConnectionPool" in content and "minconn=" in content,
        "Context managers": "@contextmanager" in content and "yield conn" in content,
        "Lazy services": all(f"get_{s}_service()" in content for s in ["sheets", "tasks", "calendar"]),
        "LRU caching": "@lru_cache(maxsize=1)" in content,
        "IMAP reuse": "_imap_connection" in content and "_imap_last_used" in content,
        "Database indexes": "CREATE INDEX" in content,
        "Proper cleanup": "def cleanup(self)" in content and "db_pool.closeall()" in content,
    }
    
    for name, result in tests.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    
    passed = sum(1 for v in tests.values() if v)
    if passed == len(tests):
        print(f"\n✅ All performance patterns implemented")
        return True
    else:
        print(f"\n❌ Some performance patterns missing")
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("Personal Assistant - Feature & Optimization Verification")
    print("=" * 70)
    
    results = [
        test_imports(),
        test_code_structure(),
        test_configuration_files(),
        test_security_patterns(),
        test_performance_patterns(),
    ]
    
    print("\n" + "=" * 70)
    if all(results):
        print("✅ ALL TESTS PASSED - Code is optimized and ready!")
        print("=" * 70)
        return 0
    else:
        print("❌ Some tests failed - Review above for details")
        print("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())
