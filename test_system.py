#!/usr/bin/env python3
"""
Online Exam Proctoring System - Quick Test Script
Tests basic functionality of the system
"""

import time
import xmlrpc.client
import requests
from student_client import StudentClient

def test_server_connection():
    """Test basic server connectivity"""
    print("Testing server connection...")
    try:
        proxy = xmlrpc.client.ServerProxy("http://127.0.0.1:8000", allow_none=True)
        result = proxy.get_status()
        if result.get("success"):
            print("✓ Server is responding")
            return True
        else:
            print("✗ Server returned error")
            return False
    except Exception as e:
        print(f"✗ Server connection failed: {e}")
        return False

def test_load_balancer():
    """Test load balancer connectivity"""
    print("Testing load balancer...")
    try:
        proxy = xmlrpc.client.ServerProxy("http://127.0.0.1:9000", allow_none=True)
        result = proxy.get_status()
        if result.get("success"):
            print("✓ Load balancer is responding")
            return True
        else:
            print("✗ Load balancer returned error")
            return False
    except Exception as e:
        print(f"✗ Load balancer connection failed: {e}")
        return False

def test_web_interface():
    """Test Flask web interface"""
    print("Testing web interface...")
    try:
        response = requests.get("http://127.0.0.1:5000", timeout=5)
        if response.status_code == 200:
            print("✓ Web interface is responding")
            return True
        else:
            print(f"✗ Web interface returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Web interface connection failed: {e}")
        return False

def test_basic_functionality():
    """Test basic system functionality"""
    print("Testing basic functionality...")
    try:
        proxy = xmlrpc.client.ServerProxy("http://127.0.0.1:8000", allow_none=True)
        
        # Test student registration
        result = proxy.register_student("TEST001")
        if not result.get("success"):
            print("✗ Student registration failed")
            return False
        
        # Test exam start
        result = proxy.start_exam()
        if not result.get("success"):
            print("✗ Exam start failed")
            return False
        
        # Test cheating detection
        result = proxy.cheating("TEST001", "test_evidence")
        if not result.get("success"):
            print("✗ Cheating detection failed")
            return False
        
        # Test exam submission
        result = proxy.submit_exam("TEST001", "manual")
        if not result.get("success"):
            print("✗ Exam submission failed")
            return False
        
        print("✓ Basic functionality working")
        return True
        
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        return False

def test_student_client():
    """Test student client functionality"""
    print("Testing student client...")
    try:
        student = StudentClient("TEST002", clock_skew=1.0)
        
        # Test registration
        if not student.register():
            print("✗ Student client registration failed")
            return False
        
        # Test time reporting
        if not student.report_time():
            print("✗ Student client time reporting failed")
            return False
        
        # Test cheating simulation
        if not student.simulate_cheating("test_evidence"):
            print("✗ Student client cheating simulation failed")
            return False
        
        student.stop()
        print("✓ Student client working")
        return True
        
    except Exception as e:
        print(f"✗ Student client test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("ONLINE EXAM PROCTORING SYSTEM - QUICK TEST")
    print("="*60)
    
    tests = [
        ("Server Connection", test_server_connection),
        ("Load Balancer", test_load_balancer),
        ("Web Interface", test_web_interface),
        ("Basic Functionality", test_basic_functionality),
        ("Student Client", test_student_client)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
        time.sleep(1)
    
    print("\n" + "="*60)
    print(f"TEST RESULTS: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("✓ All tests passed! System is working correctly.")
        return True
    else:
        print("✗ Some tests failed. Check the system components.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

