#!/usr/bin/env python3
"""
Online Exam Proctoring System - Student Client Simulation
Simulates student behavior with clock skew, cheating detection, and CS requests
"""

import time
import random
import threading
import json
import logging
from datetime import datetime
from typing import Dict, Optional
import xmlrpc.client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StudentClient:
    """Simulates a student client with clock skew and exam behavior"""
    
    def __init__(self, roll: str, server_url: str = "http://127.0.0.1:8000", 
                 clock_skew: float = 0.0, name: str = None):
        self.roll = roll
        self.name = name or f"Student_{roll}"
        self.server_url = server_url
        self.clock_skew = clock_skew  # Clock skew in seconds
        self.clock_offset = 0.0  # Applied offset from Berkeley sync
        self.lamport_clock = 0
        self.exam_status = "not_started"
        self.marks = 100.0
        self.warnings = 0
        self.last_activity = time.time()
        
        # XML-RPC proxy
        self.proxy = xmlrpc.client.ServerProxy(server_url, allow_none=True)
        
        # Threading
        self.running = False
        self.threads = []
        
        logger.info(f"Student {self.roll} initialized with clock skew {clock_skew}s")
    
    def _get_local_time(self) -> float:
        """Get local time with applied clock skew and offset"""
        return time.time() + self.clock_skew + self.clock_offset
    
    def _increment_lamport_clock(self, received_timestamp: int = None) -> int:
        """Increment and return Lamport clock value"""
        if received_timestamp is not None:
            self.lamport_clock = max(self.lamport_clock, received_timestamp) + 1
        else:
            self.lamport_clock += 1
        return self.lamport_clock
    
    def _log_event(self, event: str, data: Dict = None):
        """Log student events"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "roll": self.roll,
            "event": event,
            "data": data or {}
        }
        logger.info(f"STUDENT {self.roll}: {event} - {json.dumps(data)}")
    
    def register(self) -> bool:
        """Register with the exam coordinator"""
        try:
            result = self.proxy.register_student(self.roll)
            if result.get("success"):
                self._log_event("registered", {"server_response": result})
                return True
            else:
                logger.error(f"Registration failed: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False
    
    def start_exam(self) -> bool:
        """Wait for exam to start and update local status"""
        try:
            # Poll server until exam starts
            while True:
                result = self.proxy.get_status(self.roll)
                if result.get("success") and result.get("exam_started"):
                    self.exam_status = "in_progress"
                    self._log_event("exam_started")
                    return True
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error starting exam: {e}")
            return False
    
    def report_time(self) -> bool:
        """Report current time to server for Berkeley sync"""
        try:
            local_time = self._get_local_time()
            result = self.proxy.report_time(self.roll, local_time)
            
            if result.get("success"):
                # Apply correction from server
                if "offset" in result:
                    self.clock_offset = result["offset"]
                    self._log_event("time_corrected", {
                        "reported_time": local_time,
                        "correction": result["offset"],
                        "new_offset": self.clock_offset
                    })
                return True
            else:
                logger.error(f"Time report failed: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"Time report error: {e}")
            return False
    
    def simulate_cheating(self, evidence: str = "suspicious_activity") -> bool:
        """Simulate cheating detection and report to server"""
        try:
            self._log_event("cheating_detected", {"evidence": evidence})
            result = self.proxy.cheating(self.roll, evidence)
            
            if result.get("success"):
                action = result.get("action")
                if action == "warning":
                    self.warnings += 1
                    self.marks = result.get("new_marks", self.marks)
                    self.exam_status = "warned"
                    self._log_event("warning_received", {
                        "warnings": self.warnings,
                        "new_marks": self.marks
                    })
                elif action == "terminated":
                    self.warnings = 2
                    self.marks = 0.0
                    self.exam_status = "terminated"
                    self._log_event("terminated", {"reason": "repeated_cheating"})
                
                return True
            else:
                logger.error(f"Cheating report failed: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"Cheating simulation error: {e}")
            return False
    
    def request_critical_section(self) -> bool:
        """Request access to critical section (marksheet) using Ricart-Agrawala"""
        try:
            timestamp = self._increment_lamport_clock()
            self._log_event("cs_requested", {"timestamp": timestamp})
            
            # Send as string to avoid XML-RPC 32-bit int limit
            result = self.proxy.request_cs(self.roll, str(timestamp))
            
            if result.get("success"):
                if "holder" in result:
                    self._log_event("cs_granted", {
                        "timestamp": timestamp,
                        "holder": result["holder"]
                    })
                    return True
                else:
                    self._log_event("cs_queued", {
                        "timestamp": timestamp,
                        "position": result.get("position", "unknown")
                    })
                    return False
            else:
                logger.error(f"CS request failed: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"CS request error: {e}")
            return False
    
    def release_critical_section(self) -> bool:
        """Release critical section access"""
        try:
            result = self.proxy.release_cs(self.roll)
            
            if result.get("success"):
                self._log_event("cs_released")
                return True
            else:
                logger.error(f"CS release failed: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"CS release error: {e}")
            return False
    
    def submit_exam(self, mode: str = "manual") -> bool:
        """Submit exam (manual or auto)"""
        try:
            timestamp = self._increment_lamport_clock()
            self._log_event("exam_submit_attempt", {"mode": mode, "timestamp": timestamp})
            
            result = self.proxy.submit_exam(self.roll, mode)
            
            if result.get("success"):
                self.exam_status = "submitted"
                self._log_event("exam_submitted", {
                    "mode": mode,
                    "final_marks": result.get("final_marks", self.marks)
                })
                return True
            else:
                if result.get("reason") == "conflict_resolved":
                    self._log_event("submit_conflict", {
                        "mode": mode,
                        "winner": result.get("winner"),
                        "message": result.get("message")
                    })
                else:
                    logger.error(f"Submission failed: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"Submission error: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get current status from server"""
        try:
            result = self.proxy.get_status(self.roll)
            if result.get("success"):
                student_data = result.get("student", {})
                self.exam_status = student_data.get("status", self.exam_status)
                self.marks = student_data.get("marks", self.marks)
                self.warnings = student_data.get("warnings", self.warnings)
                self.clock_offset = student_data.get("clock_offset", self.clock_offset)
                return result
            else:
                logger.error(f"Status retrieval failed: {result.get('message')}")
                return result
        except Exception as e:
            logger.error(f"Status retrieval error: {e}")
            return {"success": False, "message": str(e)}
    
    def simulate_exam_behavior(self, duration: int = 300):
        """Simulate realistic exam behavior"""
        self.running = True
        
        def behavior_worker():
            start_time = time.time()
            last_activity = start_time
            
            while self.running and time.time() - start_time < duration:
                try:
                    # Random activities during exam
                    activity = random.choice([
                        "normal_work",
                        "time_report",
                        "cs_request",
                        "cheating_simulation"
                    ])
                    
                    if activity == "time_report":
                        self.report_time()
                    elif activity == "cs_request" and random.random() < 0.1:  # 10% chance
                        if self.request_critical_section():
                            time.sleep(random.uniform(2, 5))  # Work in CS
                            self.release_critical_section()
                    elif activity == "cheating_simulation" and random.random() < 0.05:  # 5% chance
                        if self.exam_status == "in_progress":
                            self.simulate_cheating(f"evidence_{int(time.time())}")
                    
                    # Update last activity
                    self.last_activity = time.time()
                    
                    # Sleep for random interval
                    time.sleep(random.uniform(5, 15))
                    
                except Exception as e:
                    logger.error(f"Behavior simulation error: {e}")
                    time.sleep(5)
        
        behavior_thread = threading.Thread(target=behavior_worker, daemon=True)
        behavior_thread.start()
        self.threads.append(behavior_thread)
        
        self._log_event("behavior_simulation_started", {"duration": duration})
    
    def stop(self):
        """Stop the student client"""
        self.running = False
        for thread in self.threads:
            thread.join(timeout=1)
        self._log_event("client_stopped")
    
    def run_demo(self):
        """Run a demonstration of student behavior"""
        print(f"\n=== Student {self.roll} Demo ===")
        
        # Register
        print(f"1. Registering student {self.roll}...")
        if not self.register():
            print("Registration failed!")
            return
        
        # Wait for exam start
        print("2. Waiting for exam to start...")
        if not self.start_exam():
            print("Failed to start exam!")
            return
        
        # Report time
        print("3. Reporting time for Berkeley sync...")
        self.report_time()
        
        # Simulate some activities
        print("4. Simulating exam activities...")
        self.simulate_exam_behavior(60)  # 1 minute demo
        
        # Try to access critical section
        print("5. Requesting critical section access...")
        if self.request_critical_section():
            print("   Access granted! Working in critical section...")
            time.sleep(3)
            self.release_critical_section()
            print("   Critical section released.")
        
        # Simulate cheating (first offense)
        print("6. Simulating cheating detection...")
        self.simulate_cheating("looking_at_phone")
        
        # Submit exam
        print("7. Submitting exam...")
        self.submit_exam("manual")
        
        # Get final status
        print("8. Final status:")
        status = self.get_status()
        if status.get("success"):
            student = status.get("student", {})
            print(f"   Status: {student.get('status')}")
            print(f"   Marks: {student.get('marks')}")
            print(f"   Warnings: {student.get('warnings')}")
        
        self.stop()
        print(f"=== Student {self.roll} Demo Complete ===\n")

def create_student_with_skew(roll: str, skew: float, server_url: str = "http://127.0.0.1:8000"):
    """Create a student client with specific clock skew"""
    return StudentClient(
        roll=roll,
        server_url=server_url,
        clock_skew=skew,
        name=f"Student_{roll}"
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python student_client.py <roll_number> [clock_skew] [server_url]")
        sys.exit(1)
    
    roll = sys.argv[1]
    skew = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    server_url = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8000"
    
    student = create_student_with_skew(roll, skew, server_url)
    student.run_demo()

