#!/usr/bin/env python3
"""
Online Exam Proctoring System - Demo Simulation
Demonstrates all features of the system with automated scenarios
"""

import time
import threading
import random
import json
from datetime import datetime
from student_client import StudentClient
import xmlrpc.client

class DemoSimulation:
    """Comprehensive demo of the exam proctoring system"""
    
    def __init__(self, server_url="http://127.0.0.1:8000", load_balancer_url="http://127.0.0.1:9000"):
        self.server_url = server_url
        self.load_balancer_url = load_balancer_url
        self.server_proxy = xmlrpc.client.ServerProxy(server_url, allow_none=True)
        self.balancer_proxy = xmlrpc.client.ServerProxy(load_balancer_url, allow_none=True)
        self.students = []
        self.demo_log = []
        
    def log(self, message, level="INFO"):
        """Log demo events"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        self.demo_log.append(log_entry)
    
    def wait_for_server(self, max_retries=10):
        """Wait for server to be available"""
        self.log("Checking server availability...")
        
        for i in range(max_retries):
            try:
                result = self.server_proxy.get_status()
                if result.get("success"):
                    self.log("Server is available")
                    return True
            except Exception as e:
                self.log(f"Server not ready (attempt {i+1}/{max_retries}): {e}", "WARNING")
                time.sleep(2)
        
        self.log("Server not available after maximum retries", "ERROR")
        return False
    
    def setup_students(self):
        """Create student clients with different clock skews"""
        self.log("Setting up student clients...")
        
        student_configs = [
            {"roll": "23102A0001", "skew": 2.0, "name": "Alice"},
            {"roll": "23102A0014", "skew": -3.0, "name": "Bob"},
            {"roll": "23102A0018", "skew": 5.0, "name": "Charlie"},
            {"roll": "23102A0024", "skew": -1.5, "name": "Diana"},
            {"roll": "23102A0025", "skew": 0.0, "name": "Eve"}
        ]
        
        for config in student_configs:
            student = StudentClient(
                roll=config["roll"],
                server_url=self.server_url,
                clock_skew=config["skew"],
                name=config["name"]
            )
            self.students.append(student)
            self.log(f"Created student {config['name']} ({config['roll']}) with skew {config['skew']}s")
    
    def register_students(self):
        """Register all students with the server"""
        self.log("Registering students...")
        
        for student in self.students:
            if student.register():
                self.log(f"✓ Registered {student.name} ({student.roll})")
            else:
                self.log(f"✗ Failed to register {student.name} ({student.roll})", "ERROR")
    
    def demonstrate_berkeley_sync(self):
        """Demonstrate Berkeley time synchronization"""
        self.log("\n" + "="*60)
        self.log("DEMONSTRATING BERKELEY TIME SYNCHRONIZATION")
        self.log("="*60)
        
        # Start exam to trigger time sync
        self.log("Starting exam to trigger time synchronization...")
        result = self.server_proxy.start_exam()
        if not result.get("success"):
            self.log(f"Failed to start exam: {result.get('message')}", "ERROR")
            return
        
        self.log("Exam started successfully")
        
        # Each student reports their time
        self.log("\nStudents reporting their local times:")
        for student in self.students:
            local_time = student._get_local_time()
            result = student.report_time()
            if result:
                self.log(f"  {student.name}: Local time = {local_time:.2f}s, Offset = {student.clock_offset:.2f}s")
            else:
                self.log(f"  {student.name}: Failed to report time", "ERROR")
        
        # Wait for Berkeley sync to complete
        self.log("\nWaiting for Berkeley synchronization to complete...")
        time.sleep(5)
        
        # Show final clock offsets
        self.log("\nFinal clock offsets after Berkeley sync:")
        for student in self.students:
            self.log(f"  {student.name}: Final offset = {student.clock_offset:.2f}s")
    
    def demonstrate_cheating_detection(self):
        """Demonstrate cheating detection system"""
        self.log("\n" + "="*60)
        self.log("DEMONSTRATING CHEATING DETECTION SYSTEM")
        self.log("="*60)
        
        # Select a student for cheating demonstration
        cheater = self.students[0]  # Alice
        self.log(f"Demonstrating cheating detection with {cheater.name} ({cheater.roll})")
        
        # First cheating offense
        self.log(f"\n1. First cheating offense for {cheater.name}:")
        result = cheater.simulate_cheating("looking_at_phone")
        if result:
            self.log(f"   ✓ Cheating reported successfully")
            self.log(f"   Status: {cheater.exam_status}, Warnings: {cheater.warnings}, Marks: {cheater.marks}")
        else:
            self.log(f"   ✗ Failed to report cheating", "ERROR")
        
        # Second cheating offense
        self.log(f"\n2. Second cheating offense for {cheater.name}:")
        result = cheater.simulate_cheating("copying_from_neighbor")
        if result:
            self.log(f"   ✓ Cheating reported successfully")
            self.log(f"   Status: {cheater.exam_status}, Warnings: {cheater.warnings}, Marks: {cheater.marks}")
        else:
            self.log(f"   ✗ Failed to report cheating", "ERROR")
    
    def demonstrate_ricart_agrawala(self):
        """Demonstrate Ricart-Agrawala mutual exclusion"""
        self.log("\n" + "="*60)
        self.log("DEMONSTRATING RICART-AGRAWALA MUTUAL EXCLUSION")
        self.log("="*60)
        
        # Select two students to compete for CS
        student1 = self.students[1]  # Bob
        student2 = self.students[2]  # Charlie
        
        self.log(f"Students {student1.name} and {student2.name} will compete for critical section access")
        
        # Both students request CS simultaneously
        self.log("\nBoth students requesting critical section access simultaneously...")
        
        def request_cs_async(student, delay=0):
            time.sleep(delay)
            timestamp = int(time.time() * 1000)
            result = student.request_critical_section()
            if result:
                self.log(f"  {student.name}: CS request successful")
                return True
            else:
                self.log(f"  {student.name}: CS request queued")
                return False
        
        # Start both requests with slight delay to simulate near-simultaneous requests
        thread1 = threading.Thread(target=request_cs_async, args=(student1, 0.1))
        thread2 = threading.Thread(target=request_cs_async, args=(student2, 0.2))
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Wait a bit and then release CS
        time.sleep(2)
        
        # Check who got the CS and release it
        status = self.server_proxy.get_status()
        cs_holder = status.get("cs_holder")
        
        if cs_holder:
            self.log(f"\nCritical section is held by: {cs_holder}")
            
            # Release CS
            if cs_holder == student1.roll:
                student1.release_critical_section()
                self.log(f"{student1.name} released critical section")
            elif cs_holder == student2.roll:
                student2.release_critical_section()
                self.log(f"{student2.name} released critical section")
        else:
            self.log("No one currently holds the critical section")
    
    def demonstrate_conflict_resolution(self):
        """Demonstrate conflict resolution for simultaneous submissions"""
        self.log("\n" + "="*60)
        self.log("DEMONSTRATING CONFLICT RESOLUTION")
        self.log("="*60)
        
        # Select two students for simultaneous submission
        student1 = self.students[3]  # Diana
        student2 = self.students[4]  # Eve
        
        self.log(f"Students {student1.name} and {student2.name} will submit simultaneously")
        
        def submit_async(student, mode, delay=0):
            time.sleep(delay)
            result = student.submit_exam(mode)
            if result:
                self.log(f"  {student.name}: {mode} submission successful")
            else:
                self.log(f"  {student.name}: {mode} submission failed (conflict resolved)")
            return result
        
        # Simulate simultaneous manual and auto submission
        self.log("\nSimulating simultaneous manual and auto submission...")
        
        thread1 = threading.Thread(target=submit_async, args=(student1, "manual", 0.1))
        thread2 = threading.Thread(target=submit_async, args=(student2, "auto", 0.2))
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        self.log("Conflict resolution demonstration completed")

    def demonstrate_autosave_vs_final(self):
        """Simulate autosave writes racing with final submission to show deadlock resolution"""
        self.log("\n" + "="*60)
        self.log("DEMONSTRATING AUTOSAVE VS FINAL SUBMISSION")
        self.log("="*60)

        # Ensure exam started
        status = self.server_proxy.get_status()
        if not status.get("exam_started"):
            self.server_proxy.start_exam()

        # Pick a student
        racer = self.students[0]
        roll = racer.roll

        # Fetch questions
        qres = self.server_proxy.get_questions()
        if not qres.get("success"):
            self.log("Failed to fetch questions", "ERROR")
            return
        questions = qres.get("questions", [])
        if not questions:
            self.log("No questions available", "ERROR")
            return

        stop = {"flag": False}

        def autosave_worker():
            while not stop["flag"]:
                q = random.choice(questions)
                ans = random.choice(q.get("options", ["A"]))
                lamport_ts = int(time.time() * 1000)
                res = self.server_proxy.submit_answer(roll, int(q["id"]), ans, lamport_ts, "autosave")
                self.log(f"autosave -> {res}")
                time.sleep(0.3)

        t = threading.Thread(target=autosave_worker, daemon=True)
        t.start()

        # After a short delay, attempt final submission
        time.sleep(1.5)
        self.log(f"Attempting final submission for {roll}...")
        submit_res = self.server_proxy.submit_exam(roll, "manual")
        self.log(f"final submit -> {submit_res}")

        stop["flag"] = True
        t.join(timeout=1)
    
    def demonstrate_load_balancing(self):
        """Demonstrate load balancing"""
        self.log("\n" + "="*60)
        self.log("DEMONSTRATING LOAD BALANCING")
        self.log("="*60)
        
        self.log("Testing load balancer with multiple get_status requests...")
        
        # Make multiple requests through load balancer
        for i in range(10):
            try:
                result = self.balancer_proxy.get_status()
                if result.get("success"):
                    self.log(f"  Request {i+1}: Success")
                else:
                    self.log(f"  Request {i+1}: Failed", "ERROR")
            except Exception as e:
                self.log(f"  Request {i+1}: Error - {e}", "ERROR")
            
            time.sleep(0.5)
        
        # Get load balancer statistics
        try:
            stats = self.balancer_proxy.get_stats()
            self.log(f"\nLoad balancer statistics:")
            self.log(f"  Total requests: {stats.get('total_requests', 0)}")
            self.log(f"  Backend status: {stats.get('backend_status', {})}")
            self.log(f"  Request distribution: {stats.get('request_count', {})}")
        except Exception as e:
            self.log(f"Failed to get load balancer stats: {e}", "ERROR")
    
    def demonstrate_replication(self):
        """Demonstrate data replication (simulated)"""
        self.log("\n" + "="*60)
        self.log("DEMONSTRATING DATA REPLICATION")
        self.log("="*60)
        
        self.log("Simulating data replication scenario...")
        
        # Simulate adding a new student through load balancer
        test_roll = "TEST001"
        self.log(f"Adding test student {test_roll} through load balancer...")
        
        try:
            result = self.balancer_proxy.register_student(test_roll)
            if result.get("success"):
                self.log(f"✓ Student {test_roll} registered successfully")
                
                # Verify student exists
                status = self.balancer_proxy.get_status(test_roll)
                if status.get("success"):
                    self.log(f"✓ Student {test_roll} verified in system")
                else:
                    self.log(f"✗ Student {test_roll} not found in system", "ERROR")
            else:
                self.log(f"✗ Failed to register student {test_roll}: {result.get('message')}", "ERROR")
        except Exception as e:
            self.log(f"Error in replication demo: {e}", "ERROR")
    
    def run_comprehensive_demo(self):
        """Run the complete demonstration"""
        self.log("="*80)
        self.log("ONLINE EXAM PROCTORING SYSTEM - COMPREHENSIVE DEMO")
        self.log("="*80)
        
        # Check server availability
        if not self.wait_for_server():
            self.log("Cannot proceed without server", "ERROR")
            return
        
        try:
            # Setup
            self.setup_students()
            self.register_students()
            
            # Run demonstrations
            self.demonstrate_berkeley_sync()
            self.demonstrate_cheating_detection()
            self.demonstrate_ricart_agrawala()
            self.demonstrate_conflict_resolution()
            self.demonstrate_autosave_vs_final()
            self.demonstrate_load_balancing()
            self.demonstrate_replication()
            
            # Final status
            self.log("\n" + "="*60)
            self.log("FINAL SYSTEM STATUS")
            self.log("="*60)
            
            status = self.server_proxy.get_status()
            if status.get("success"):
                students = status.get("students", {})
                self.log(f"Total students: {len(students)}")
                
                for roll, student in students.items():
                    self.log(f"  {roll}: {student['status']}, {student['marks']} marks, {student['warnings']} warnings")
            
            self.log("\n" + "="*80)
            self.log("DEMO COMPLETED SUCCESSFULLY")
            self.log("="*80)
            
        except Exception as e:
            self.log(f"Demo failed with error: {e}", "ERROR")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            self.log("\nCleaning up...")
            for student in self.students:
                student.stop()

def main():
    """Main function to run the demo"""
    import sys
    
    server_url = "http://127.0.0.1:8000"
    balancer_url = "http://127.0.0.1:9000"
    
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    if len(sys.argv) > 2:
        balancer_url = sys.argv[2]
    
    print("Online Exam Proctoring System - Demo Simulation")
    print(f"Server URL: {server_url}")
    print(f"Load Balancer URL: {balancer_url}")
    print("\nMake sure the server and load balancer are running before starting the demo.")
    print("Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\nDemo cancelled.")
        return
    
    demo = DemoSimulation(server_url, balancer_url)
    demo.run_comprehensive_demo()

if __name__ == "__main__":
    main()

