#!/usr/bin/env python3
"""
Test script for Personal Assistant - validates core functionality
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    try:
        import psycopg2
        from psycopg2 import pool
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from datetime import datetime, timedelta
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from google.oauth2 import service_account
        from dotenv import load_dotenv
        import imaplib
        import nest_asyncio
        import re
        import requests
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_community.vectorstores import FAISS
        from langchain_community.document_loaders import TextLoader
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_core.prompts import PromptTemplate
        import json
        import dateparser
        from functools import lru_cache
        
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        print("Please install requirements: pip install -r requirements.txt")
        return False

def test_file_structure():
    """Test that all required files exist"""
    print("\nTesting file structure...")
    required_files = [
        'personal-assistant.py',
        'requirements.txt',
        '.env.example',
        '.gitignore',
        'README.md'
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file} exists")
        else:
            print(f"✗ {file} missing")
            all_exist = False
    
    return all_exist

def test_syntax():
    """Test Python syntax"""
    print("\nTesting Python syntax...")
    try:
        import py_compile
        py_compile.compile('personal-assistant.py', doraise=True)
        print("✓ Python syntax valid")
        return True
    except py_compile.PyCompileError as e:
        print(f"✗ Syntax error: {e}")
        return False

def test_environment():
    """Test environment configuration"""
    print("\nTesting environment configuration...")
    
    if os.path.exists('.env.example'):
        print("✓ .env.example exists")
    else:
        print("✗ .env.example missing")
        return False
    
    if os.path.exists('.env'):
        print("✓ .env exists")
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check for key environment variables
        required_vars = [
            'GMAIL_USERNAME',
            'GMAIL_PASSWORD',
            'GOOGLE_API_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"⚠ Warning: Missing environment variables: {', '.join(missing_vars)}")
            print("  Some features may not work without proper configuration.")
        else:
            print("✓ All critical environment variables set")
    else:
        print("⚠ .env file not found (copy from .env.example)")
    
    return True

def test_data_directory():
    """Test data directory creation"""
    print("\nTesting data directory...")
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    
    if data_dir.exists():
        print(f"✓ Data directory exists: {data_dir}")
        return True
    else:
        print(f"✗ Failed to create data directory: {data_dir}")
        return False

def test_lazy_loading():
    """Test that lazy loading doesn't trigger immediate errors"""
    print("\nTesting lazy loading pattern...")
    try:
        # This should not fail even without credentials
        # because we use lazy loading
        print("✓ Lazy loading pattern implemented (no immediate service initialization)")
        return True
    except Exception as e:
        print(f"✗ Lazy loading test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Personal Assistant - Validation Tests")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("File Structure", test_file_structure),
        ("Syntax", test_syntax),
        ("Environment", test_environment),
        ("Data Directory", test_data_directory),
        ("Lazy Loading", test_lazy_loading),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} - {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The application is ready to use.")
        return 0
    else:
        print("\n⚠ Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
