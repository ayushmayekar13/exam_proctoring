#!/usr/bin/env python3
"""
Unit tests for the student client
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from student_client import StudentClient

class TestStudentClient(unittest.TestCase):
    """Test cases for StudentClient class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.student = StudentClient(
            roll="23102A0001",
            server_url="http://127.0.0.1:8000",
            clock_skew=2.0,
            name="TestStudent"
        )
    
    def tearDown(self):
        """Clean up after tests"""
        self.student.stop()
    
    def test_initialization(self):
        """Test student client initialization"""
        self.assertEqual(self.student.roll, "23102A0001")
        self.assertEqual(self.student.name, "TestStudent")
        self.assertEqual(self.student.clock_skew, 2.0)
        self.assertEqual(self.student.exam_status, "not_started")
        self.assertEqual(self.student.marks, 100.0)
        self.assertEqual(self.student.warnings, 0)
        self.assertEqual(self.student.lamport_clock, 0)
    
    def test_get_local_time(self):
        """Test local time calculation with clock skew"""
        # Mock time.time() to return a fixed value
        with patch('time.time', return_value=1000.0):
            local_time = self.student._get_local_time()
            expected_time = 1000.0 + 2.0 + 0.0  # base_time + skew + offset
            self.assertEqual(local_time, expected_time)
    
    def test_lamport_clock(self):
        """Test Lamport clock functionality"""
        # Test initial clock
        self.assertEqual(self.student.lamport_clock, 0)
        
        # Test increment without received timestamp
        clock1 = self.student._increment_lamport_clock()
        self.assertEqual(clock1, 1)
        self.assertEqual(self.student.lamport_clock, 1)
        
        # Test increment with received timestamp
        clock2 = self.student._increment_lamport_clock(100)
        self.assertEqual(clock2, 101)
        self.assertEqual(self.student.lamport_clock, 101)
        
        # Test increment with lower received timestamp
        clock3 = self.student._increment_lamport_clock(50)
        self.assertEqual(clock3, 102)  # Should use current clock + 1
    
    @patch('xmlrpc.client.ServerProxy')
    def test_register(self, mock_server_proxy):
        """Test student registration"""
        # Mock server response
        mock_proxy = Mock()
        mock_proxy.register_student.return_value = {"success": True, "message": "Student registered"}
        mock_server_proxy.return_value = mock_proxy
        
        # Test successful registration
        result = self.student.register()
        self.assertTrue(result)
        mock_proxy.register_student.assert_called_once_with("23102A0001")
        
        # Test failed registration
        mock_proxy.register_student.return_value = {"success": False, "message": "Registration failed"}
        result = self.student.register()
        self.assertFalse(result)
    
    @patch('xmlrpc.client.ServerProxy')
    def test_start_exam(self, mock_server_proxy):
        """Test exam start functionality"""
        # Mock server response
        mock_proxy = Mock()
        mock_proxy.get_status.return_value = {
            "success": True,
            "exam_started": True,
            "student": {"status": "in_progress"}
        }
        mock_server_proxy.return_value = mock_proxy
        
        # Test exam start
        result = self.student.start_exam()
        self.assertTrue(result)
        self.assertEqual(self.student.exam_status, "in_progress")
    
    @patch('xmlrpc.client.ServerProxy')
    def test_report_time(self, mock_server_proxy):
        """Test time reporting functionality"""
        # Mock server response
        mock_proxy = Mock()
        mock_proxy.report_time.return_value = {"success": True, "offset": 1.5}
        mock_server_proxy.return_value = mock_proxy
        
        # Test time reporting
        result = self.student.report_time()
        self.assertTrue(result)
        self.assertEqual(self.student.clock_offset, 1.5)
        mock_proxy.report_time.assert_called_once()
    
    @patch('xmlrpc.client.ServerProxy')
    def test_simulate_cheating(self, mock_server_proxy):
        """Test cheating simulation"""
        # Mock server response for first offense
        mock_proxy = Mock()
        mock_proxy.cheating.return_value = {
            "success": True,
            "action": "warning",
            "new_marks": 50.0
        }
        mock_server_proxy.return_value = mock_proxy
        
        # Test first cheating offense
        result = self.student.simulate_cheating("evidence")
        self.assertTrue(result)
        self.assertEqual(self.student.warnings, 1)
        self.assertEqual(self.student.marks, 50.0)
        self.assertEqual(self.student.exam_status, "warned")
        
        # Mock server response for second offense
        mock_proxy.cheating.return_value = {
            "success": True,
            "action": "terminated"
        }
        
        # Test second cheating offense
        result = self.student.simulate_cheating("evidence2")
        self.assertTrue(result)
        self.assertEqual(self.student.warnings, 2)
        self.assertEqual(self.student.marks, 0.0)
        self.assertEqual(self.student.exam_status, "terminated")
    
    @patch('xmlrpc.client.ServerProxy')
    def test_request_critical_section(self, mock_server_proxy):
        """Test critical section request"""
        # Mock server response
        mock_proxy = Mock()
        mock_proxy.request_cs.return_value = {
            "success": True,
            "message": "Request queued",
            "position": 1
        }
        mock_server_proxy.return_value = mock_proxy
        
        # Test CS request
        result = self.student.request_critical_section()
        self.assertFalse(result)  # Not granted immediately
        mock_proxy.request_cs.assert_called_once()
    
    @patch('xmlrpc.client.ServerProxy')
    def test_submit_exam(self, mock_server_proxy):
        """Test exam submission"""
        # Mock server response
        mock_proxy = Mock()
        mock_proxy.submit_exam.return_value = {
            "success": True,
            "message": "Exam submitted successfully",
            "final_marks": 85.0
        }
        mock_server_proxy.return_value = mock_proxy
        
        # Test exam submission
        result = self.student.submit_exam("manual")
        self.assertTrue(result)
        self.assertEqual(self.student.exam_status, "submitted")
        mock_proxy.submit_exam.assert_called_once_with("23102A0001", "manual")
    
    @patch('xmlrpc.client.ServerProxy')
    def test_get_status(self, mock_server_proxy):
        """Test status retrieval"""
        # Mock server response
        mock_proxy = Mock()
        mock_proxy.get_status.return_value = {
            "success": True,
            "student": {
                "status": "in_progress",
                "marks": 90.0,
                "warnings": 0,
                "clock_offset": 1.0
            }
        }
        mock_server_proxy.return_value = mock_proxy
        
        # Test status retrieval
        result = self.student.get_status()
        self.assertTrue(result["success"])
        self.assertEqual(self.student.exam_status, "in_progress")
        self.assertEqual(self.student.marks, 90.0)
        self.assertEqual(self.student.warnings, 0)
        self.assertEqual(self.student.clock_offset, 1.0)
    
    def test_clock_skew_simulation(self):
        """Test clock skew simulation"""
        # Test with different clock skews
        skews = [0.0, 2.0, -3.0, 5.0]
        
        for skew in skews:
            student = StudentClient("TEST001", clock_skew=skew)
            with patch('time.time', return_value=1000.0):
                local_time = student._get_local_time()
                expected_time = 1000.0 + skew
                self.assertEqual(local_time, expected_time)
            student.stop()
    
    def test_behavior_simulation(self):
        """Test behavior simulation"""
        # Mock server proxy
        with patch('xmlrpc.client.ServerProxy') as mock_server_proxy:
            mock_proxy = Mock()
            mock_proxy.get_status.return_value = {
                "success": True,
                "exam_started": True,
                "student": {"status": "in_progress"}
            }
            mock_proxy.report_time.return_value = {"success": True, "offset": 0.0}
            mock_proxy.cheating.return_value = {"success": True, "action": "warning", "new_marks": 50.0}
            mock_server_proxy.return_value = mock_proxy
            
            # Start behavior simulation
            self.student.simulate_exam_behavior(1)  # 1 second simulation
            
            # Let it run briefly
            time.sleep(0.5)
            
            # Stop simulation
            self.student.stop()
            
            # Verify some methods were called
            self.assertTrue(mock_proxy.get_status.called or mock_proxy.report_time.called)

class TestStudentClientIntegration(unittest.TestCase):
    """Integration tests for student client"""
    
    def test_full_student_workflow(self):
        """Test complete student workflow"""
        with patch('xmlrpc.client.ServerProxy') as mock_server_proxy:
            mock_proxy = Mock()
            mock_server_proxy.return_value = mock_proxy
            
            # Mock all server responses
            mock_proxy.register_student.return_value = {"success": True}
            mock_proxy.get_status.return_value = {
                "success": True,
                "exam_started": True,
                "student": {"status": "in_progress"}
            }
            mock_proxy.report_time.return_value = {"success": True, "offset": 1.0}
            mock_proxy.cheating.return_value = {"success": True, "action": "warning", "new_marks": 50.0}
            mock_proxy.submit_exam.return_value = {"success": True, "final_marks": 50.0}
            
            # Create student
            student = StudentClient("23102A0001", clock_skew=2.0)
            
            # Test full workflow
            self.assertTrue(student.register())
            self.assertTrue(student.start_exam())
            self.assertTrue(student.report_time())
            self.assertTrue(student.simulate_cheating("evidence"))
            self.assertTrue(student.submit_exam("manual"))
            
            # Verify final state
            self.assertEqual(student.exam_status, "submitted")
            self.assertEqual(student.marks, 50.0)
            self.assertEqual(student.warnings, 1)
            
            student.stop()

if __name__ == "__main__":
    unittest.main()

