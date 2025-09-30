#!/usr/bin/env python3
"""
Unit tests for the exam coordinator server
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import ExamCoordinator

class TestExamCoordinator(unittest.TestCase):
    """Test cases for ExamCoordinator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.coordinator = ExamCoordinator(port=8000, replica_id="test")
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_register_student(self):
        """Test student registration"""
        # Test successful registration
        result = self.coordinator.register_student("23102A0001")
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Student 23102A0001 registered successfully")
        
        # Test duplicate registration
        result = self.coordinator.register_student("23102A0001")
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Student already registered")
        
        # Test empty roll number
        result = self.coordinator.register_student("")
        self.assertFalse(result["success"])
    
    def test_start_exam(self):
        """Test exam start functionality"""
        # Test starting exam without students
        result = self.coordinator.start_exam()
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No students registered")
        
        # Register a student
        self.coordinator.register_student("23102A0001")
        
        # Test starting exam
        result = self.coordinator.start_exam()
        self.assertTrue(result["success"])
        self.assertTrue(self.coordinator.exam_started)
        
        # Test starting exam again
        result = self.coordinator.start_exam()
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Exam already started")
    
    def test_cheating_detection(self):
        """Test cheating detection system"""
        # Register a student
        self.coordinator.register_student("23102A0001")
        
        # Test cheating with invalid roll
        result = self.coordinator.cheating("invalid_roll", "evidence")
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Invalid roll number")
        
        # Test first cheating offense
        result = self.coordinator.cheating("23102A0001", "looking_at_phone")
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "warning")
        self.assertEqual(self.coordinator.students["23102A0001"]["warnings"], 1)
        self.assertEqual(self.coordinator.students["23102A0001"]["marks"], 50.0)
        self.assertEqual(self.coordinator.students["23102A0001"]["status"], "warned")
        
        # Test second cheating offense
        result = self.coordinator.cheating("23102A0001", "copying_from_neighbor")
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "terminated")
        self.assertEqual(self.coordinator.students["23102A0001"]["warnings"], 2)
        self.assertEqual(self.coordinator.students["23102A0001"]["marks"], 0.0)
        self.assertEqual(self.coordinator.students["23102A0001"]["status"], "terminated")
    
    def test_exam_submission(self):
        """Test exam submission functionality"""
        # Register a student
        self.coordinator.register_student("23102A0001")
        
        # Test submission with invalid roll
        result = self.coordinator.submit_exam("invalid_roll", "manual")
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Invalid roll number")
        
        # Test manual submission
        result = self.coordinator.submit_exam("23102A0001", "manual")
        self.assertTrue(result["success"])
        self.assertEqual(self.coordinator.students["23102A0001"]["status"], "submitted")
        self.assertEqual(self.coordinator.students["23102A0001"]["submission_mode"], "manual")
        
        # Test submission after already submitted
        result = self.coordinator.submit_exam("23102A0001", "auto")
        self.assertFalse(result["success"])
        self.assertIn("already submitted", result["message"])
    
    def test_time_reporting(self):
        """Test time reporting for Berkeley sync"""
        # Register a student
        self.coordinator.register_student("23102A0001")
        
        # Test time reporting
        current_time = time.time()
        result = self.coordinator.report_time("23102A0001", current_time)
        self.assertTrue(result["success"])
        self.assertIn("offset", result)
        
        # Test with invalid roll
        result = self.coordinator.report_time("invalid_roll", current_time)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Invalid roll number")
    
    def test_critical_section_requests(self):
        """Test critical section request functionality"""
        # Register a student
        self.coordinator.register_student("23102A0001")
        
        # Test CS request
        result = self.coordinator.request_cs("23102A0001", 1000)
        self.assertTrue(result["success"])
        
        # Test CS reply
        result = self.coordinator.reply_cs("23102A0001", 1001)
        self.assertTrue(result["success"])
        
        # Test CS release
        result = self.coordinator.release_cs("23102A0001")
        self.assertTrue(result["success"])
    
    def test_get_status(self):
        """Test status retrieval"""
        # Test getting status without students
        result = self.coordinator.get_status()
        self.assertTrue(result["success"])
        self.assertEqual(len(result["students"]), 0)
        
        # Register a student
        self.coordinator.register_student("23102A0001")
        
        # Test getting all students status
        result = self.coordinator.get_status()
        self.assertTrue(result["success"])
        self.assertEqual(len(result["students"]), 1)
        self.assertIn("23102A0001", result["students"])
        
        # Test getting specific student status
        result = self.coordinator.get_status("23102A0001")
        self.assertTrue(result["success"])
        self.assertIn("student", result)
        self.assertEqual(result["student"]["status"], "not_started")
    
    def test_end_exam(self):
        """Test exam ending functionality"""
        # Test ending exam that hasn't started
        result = self.coordinator.end_exam()
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Exam not started")
        
        # Register students and start exam
        self.coordinator.register_student("23102A0001")
        self.coordinator.register_student("23102A0002")
        self.coordinator.start_exam()
        
        # End exam
        result = self.coordinator.end_exam()
        self.assertTrue(result["success"])
        self.assertTrue(self.coordinator.exam_ended)
        self.assertFalse(self.coordinator.exam_started)
    
    def test_lamport_clock(self):
        """Test Lamport clock functionality"""
        # Test initial clock value
        initial_clock = self.coordinator.lamport_clock
        
        # Test increment without received timestamp
        clock1 = self.coordinator._increment_lamport_clock()
        self.assertEqual(clock1, initial_clock + 1)
        
        # Test increment with received timestamp
        clock2 = self.coordinator._increment_lamport_clock(1000)
        self.assertEqual(clock2, 1001)
        
        # Test increment with lower received timestamp
        clock3 = self.coordinator._increment_lamport_clock(500)
        self.assertEqual(clock3, 1002)  # Should use current clock + 1
    
    def test_conflict_resolution(self):
        """Test conflict resolution for simultaneous submissions"""
        # Register a student
        self.coordinator.register_student("23102A0001")
        
        # Simulate simultaneous submissions
        def submit_exam_async(mode, delay=0):
            time.sleep(delay)
            return self.coordinator.submit_exam("23102A0001", mode)
        
        # Start two submission threads
        thread1 = threading.Thread(target=submit_exam_async, args=("manual", 0.1))
        thread2 = threading.Thread(target=submit_exam_async, args=("auto", 0.2))
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Check that only one submission was successful
        student = self.coordinator.students["23102A0001"]
        self.assertEqual(student["status"], "submitted")
        self.assertIn(student["submission_mode"], ["manual", "auto"])

class TestExamCoordinatorIntegration(unittest.TestCase):
    """Integration tests for the exam coordinator"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.coordinator = ExamCoordinator(port=8000, replica_id="test")
    
    def test_full_exam_workflow(self):
        """Test complete exam workflow"""
        # Register students
        students = ["23102A0001", "23102A0002", "23102A0003"]
        for roll in students:
            result = self.coordinator.register_student(roll)
            self.assertTrue(result["success"])
        
        # Start exam
        result = self.coordinator.start_exam()
        self.assertTrue(result["success"])
        
        # Simulate some cheating
        result = self.coordinator.cheating("23102A0001", "evidence1")
        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "warning")
        
        # Simulate submissions
        result = self.coordinator.submit_exam("23102A0002", "manual")
        self.assertTrue(result["success"])
        
        result = self.coordinator.submit_exam("23102A0003", "auto")
        self.assertTrue(result["success"])
        
        # End exam
        result = self.coordinator.end_exam()
        self.assertTrue(result["success"])
        
        # Verify final status
        status = self.coordinator.get_status()
        self.assertTrue(status["success"])
        self.assertEqual(len(status["students"]), 3)
        
        # Check individual student statuses
        students_data = status["students"]
        self.assertEqual(students_data["23102A0001"]["status"], "warned")
        self.assertEqual(students_data["23102A0002"]["status"], "submitted")
        self.assertEqual(students_data["23102A0003"]["status"], "submitted")

if __name__ == "__main__":
    unittest.main()

