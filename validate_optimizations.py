#!/usr/bin/env python3
"""
Validation script to verify Personal Assistant optimizations
"""
import os
import sys
import time
from pathlib import Path

def check_requirements():
    """Check if requirements.txt exists and has all necessary packages"""
    print("Checking requirements.txt...")
    req_file = Path("requirements.txt")
    if not req_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    with open(req_file) as f:
        content = f.read()
        required_packages = [
            "python-dotenv", "psycopg2-binary", "langchain",
            "google-api-python-client", "faiss-cpu", "APScheduler"
        ]
        missing = [pkg for pkg in required_packages if pkg not in content]
        if missing:
            print(f"❌ Missing packages: {', '.join(missing)}")
            return False
    
    print("✅ requirements.txt is complete")
    return True

def check_env_example():
    """Check if .env.example exists with all required variables"""
    print("\nChecking .env.example...")
    env_file = Path(".env.example")
    if not env_file.exists():
        print("❌ .env.example not found")
        return False
    
    with open(env_file) as f:
        content = f.read()
        required_vars = [
            "GOOGLE_API_KEY", "DB_HOST", "DB_USER", "DB_PASSWORD",
            "GMAIL_USERNAME", "GMAIL_PASSWORD", "SERVICE_ACCOUNT_FILE"
        ]
        missing = [var for var in required_vars if var not in content]
        if missing:
            print(f"❌ Missing variables: {', '.join(missing)}")
            return False
    
    print("✅ .env.example is complete")
    return True

def check_gitignore():
    """Check if .gitignore protects sensitive files"""
    print("\nChecking .gitignore...")
    gitignore_file = Path(".gitignore")
    if not gitignore_file.exists():
        print("❌ .gitignore not found")
        return False
    
    with open(gitignore_file) as f:
        content = f.read()
        required_patterns = [".env", "*.json", "__pycache__", "data/"]
        missing = [pat for pat in required_patterns if pat not in content]
        if missing:
            print(f"❌ Missing patterns: {', '.join(missing)}")
            return False
    
    print("✅ .gitignore protects sensitive files")
    return True

def check_code_structure():
    """Check if the code has optimized structures"""
    print("\nChecking code structure...")
    code_file = Path("personal-assistant.py")
    if not code_file.exists():
        print("❌ personal-assistant.py not found")
        return False
    
    with open(code_file) as f:
        content = f.read()
        
        # Check for optimizations
        checks = {
            "Connection pooling": "ThreadedConnectionPool" in content,
            "Context managers": "@contextmanager" in content,
            "Lazy loading": "@lru_cache" in content,
            "Environment validation": "REQUIRED_ENV_VARS" in content,
            "Resource cleanup": "def cleanup(self)" in content,
            "IMAP reuse": "_get_imap_connection" in content,
            "Lazy Google services": "get_sheets_service()" in content,
            "No hard-coded credentials": "postgres.ixruzjparquranqfdvdm" not in content,
        }
        
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            print(f"❌ Missing optimizations: {', '.join(failed)}")
            return False
    
    print("✅ Code structure has all optimizations")
    return True

def check_documentation():
    """Check if README.md has been updated"""
    print("\nChecking documentation...")
    readme = Path("README.md")
    if not readme.exists():
        print("❌ README.md not found")
        return False
    
    with open(readme) as f:
        content = f.read()
        required_sections = [
            "Performance Optimizations",
            "Installation",
            "Configuration",
            "Database Schema"
        ]
        missing = [sec for sec in required_sections if sec not in content]
        if missing:
            print(f"❌ Missing sections: {', '.join(missing)}")
            return False
    
    print("✅ Documentation is comprehensive")
    return True

def main():
    """Run all validation checks"""
    print("=" * 60)
    print("Personal Assistant Optimization Validation")
    print("=" * 60)
    
    checks = [
        check_requirements,
        check_env_example,
        check_gitignore,
        check_code_structure,
        check_documentation
    ]
    
    results = [check() for check in checks]
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL CHECKS PASSED - Optimizations verified!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some checks failed - Please review above")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
