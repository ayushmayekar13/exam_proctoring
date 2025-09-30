#!/usr/bin/env python3
"""
Online Exam Proctoring System - Main Coordinator Server
Implements XML-RPC server with cheating detection, time sync, and mutual exclusion
"""

import time
import threading
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
import xmlrpc.client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('exam_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ExamCoordinator:
    """Main coordinator for the exam proctoring system"""
    
    def __init__(self, port: int = 8000, replica_id: str = "master"):
        self.port = port
        self.replica_id = replica_id
        self.students: Dict[str, Dict] = {}
        self.exam_started = False
        self.exam_ended = False
        self.lamport_clock = 0
        self.cs_holder = None  # Who currently holds the critical section
        self.cs_queue = []  # Queue for Ricart-Agrawala requests
        self.received_replies = set()  # Track received replies for RA
        self.pending_requests = {}  # Track pending CS requests
        self.replicas = []  # List of replica servers for replication
        self.version_counter = 0  # For replication consistency
        
        # Exam questions and storage (in-memory abstraction)
        self.questions: List[Dict] = [
            {"id": 1, "text": "2 + 2 = ?", "options": ["3", "4", "5"], "answer": "4"},
            {"id": 2, "text": "Capital of France?", "options": ["Paris", "Rome", "Berlin"], "answer": "Paris"},
            {"id": 3, "text": "HTTP status for Not Found?", "options": ["200", "404", "500"], "answer": "404"},
        ]
        self.exam_duration_seconds = 300
        self.exam_start_monotonic: Optional[float] = None
        
        # Answer storage with versioning for eventual consistency
        # answers[roll][question_id] = { value, version, lamport_ts, last_write_mode }
        self.answers: Dict[str, Dict[int, Dict]] = {}
        self.final_submissions: Dict[str, Dict] = {}
        
        # Locks to avoid deadlock between autosave and final submit
        self.answers_lock = threading.Lock()
        self.submit_lock = threading.Lock()
        
        # Berkeley time sync
        self.time_sync_data = {}
        self.last_sync_time = 0
        
        # Thread locks
        self.lock = threading.Lock()
        self.cs_lock = threading.Lock()
        
        logger.info(f"Exam Coordinator {replica_id} initialized on port {port}")
    
    def _increment_lamport_clock(self, received_timestamp: int = None) -> int:
        """Increment and return Lamport clock value"""
        with self.lock:
            if received_timestamp is not None:
                self.lamport_clock = max(self.lamport_clock, received_timestamp) + 1
            else:
                self.lamport_clock += 1
            return self.lamport_clock
    
    def _log_event(self, event: str, data: Dict = None):
        """Log system events with timestamp"""
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "replica_id": self.replica_id,
            "event": event,
            "data": data or {}
        }
        logger.info(f"EVENT: {event} - {json.dumps(data)}")
        
        # Write to common log file
        with open("common.txt", "a") as f:
            f.write(f"{timestamp} [{self.replica_id}] {event}: {json.dumps(data)}\n")
    
    def register_student(self, roll: str) -> Dict:
        """Register a new student for the exam"""
        try:
            with self.lock:
                if roll in self.students:
                    return {"success": False, "message": "Student already registered"}
                
                self.students[roll] = {
                    "status": "not_started",
                    "warnings": 0,
                    "marks": 100.0,
                    "clock_offset": 0.0,
                    "last_activity": time.time(),
                    "registered_at": time.time()
                }
                
                self._log_event("student_registered", {"roll": roll})
                return {"success": True, "message": f"Student {roll} registered successfully"}
                
        except Exception as e:
            logger.error(f"Error registering student {roll}: {e}")
            return {"success": False, "message": f"Registration failed: {str(e)}"}
    
    def start_exam(self) -> Dict:
        """Start the exam for all registered students"""
        try:
            with self.lock:
                if self.exam_started:
                    return {"success": False, "message": "Exam already started"}
                
                if not self.students:
                    return {"success": False, "message": "No students registered"}
                
                # Update all students to in_progress
                for roll in self.students:
                    self.students[roll]["status"] = "in_progress"
                    self.students[roll]["last_activity"] = time.time()
                
                self.exam_started = True
                self.exam_start_monotonic = time.monotonic()
                self._log_event("exam_started", {"student_count": len(self.students)})
                
                # Start Berkeley time sync
                self._start_berkeley_sync()
                
                return {"success": True, "message": "Exam started successfully"}
                
        except Exception as e:
            logger.error(f"Error starting exam: {e}")
            return {"success": False, "message": f"Failed to start exam: {str(e)}"}
    
    def cheating(self, roll: str, evidence: str) -> Dict:
        """Handle cheating detection for a student"""
        try:
            with self.lock:
                if roll not in self.students:
                    return {"success": False, "message": "Invalid roll number"}
                
                student = self.students[roll]
                warnings = student["warnings"]
                marks = student["marks"]
                
                self._log_event("cheating_detected", {
                    "roll": roll, 
                    "evidence": evidence, 
                    "current_warnings": warnings,
                    "current_marks": marks
                })
                
                if warnings == 0:
                    # First offense
                    student["warnings"] = 1
                    student["marks"] = marks * 0.5  # Deduct 50%
                    student["status"] = "warned"
                    student["last_activity"] = time.time()
                    
                    return {
                        "success": True,
                        "action": "warning",
                        "new_marks": student["marks"],
                        "message": f"First warning for {roll}. Marks reduced to {student['marks']:.1f}"
                    }
                
                elif warnings >= 1:
                    # Second offense - terminate
                    student["warnings"] = 2
                    student["marks"] = 0.0
                    student["status"] = "terminated"
                    student["last_activity"] = time.time()
                    
                    return {
                        "success": True,
                        "action": "terminated",
                        "message": f"Student {roll} terminated due to repeated cheating"
                    }
                
                return {"success": True, "action": "no_change", "message": "No further action needed"}
                
        except Exception as e:
            logger.error(f"Error handling cheating for {roll}: {e}")
            return {"success": False, "message": f"Cheating detection failed: {str(e)}"}
    
    def submit_exam(self, roll: str, mode: str) -> Dict:
        """Handle exam submission (manual or auto)"""
        try:
            # Prevent deadlock: acquire submit_lock first, then main lock
            with self.submit_lock, self.lock:
                if roll not in self.students:
                    return {"success": False, "message": "Invalid roll number"}
                
                student = self.students[roll]
                if student["status"] in ["terminated", "submitted"]:
                    return {"success": False, "message": "Student already submitted or terminated"}
                
                # Check for conflicts with simultaneous submissions
                conflict_key = f"submit_{roll}"
                current_time = self._increment_lamport_clock()
                
                # Use atomic compare-and-set for conflict resolution
                if hasattr(self, '_submission_locks'):
                    if conflict_key in self._submission_locks:
                        return {
                            "success": False,
                            "reason": "conflict_resolved",
                            "winner": roll,
                            "message": "Submission already in progress"
                        }
                    self._submission_locks[conflict_key] = current_time
                else:
                    self._submission_locks = {conflict_key: current_time}
                
                # Mark final submission snapshot (for conflict resolution with autosave)
                self.final_submissions[roll] = {
                    "lamport_ts": current_time,
                    "mode": mode,
                    "version": self.version_counter + 1
                }

                student["status"] = "submitted"
                student["last_activity"] = time.time()
                student["submission_mode"] = mode
                student["submission_time"] = current_time
                
                self._log_event("exam_submitted", {
                    "roll": roll, 
                    "mode": mode, 
                    "timestamp": current_time,
                    "final_marks": student["marks"]
                })
                
                return {
                    "success": True,
                    "message": f"Exam submitted successfully via {mode} mode",
                    "final_marks": student["marks"]
                }
                
        except Exception as e:
            logger.error(f"Error submitting exam for {roll}: {e}")
            return {"success": False, "message": f"Submission failed: {str(e)}"}
    
    def report_time(self, roll: str, reported_time: float) -> Dict:
        """Report time for Berkeley synchronization"""
        try:
            with self.lock:
                if roll not in self.students:
                    return {"success": False, "message": "Invalid roll number"}
                
                server_time = time.time()
                offset = reported_time - server_time
                
                self.time_sync_data[roll] = {
                    "reported_time": reported_time,
                    "server_time": server_time,
                    "offset": offset,
                    "timestamp": time.time()
                }
                
                self._log_event("time_reported", {
                    "roll": roll, 
                    "reported_time": reported_time,
                    "offset": offset
                })
                
                return {"success": True, "offset": offset}
                
        except Exception as e:
            logger.error(f"Error reporting time for {roll}: {e}")
            return {"success": False, "message": f"Time report failed: {str(e)}"}
    
    def _start_berkeley_sync(self):
        """Start Berkeley time synchronization process"""
        def sync_worker():
            while self.exam_started and not self.exam_ended:
                try:
                    if len(self.time_sync_data) >= 2:  # Need at least 2 participants
                        self._perform_berkeley_sync()
                    time.sleep(30)  # Sync every 30 seconds
                except Exception as e:
                    logger.error(f"Berkeley sync error: {e}")
                    time.sleep(5)
        
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
        logger.info("Berkeley time synchronization started")
    
    def _perform_berkeley_sync(self):
        """Perform Berkeley time synchronization algorithm"""
        try:
            # Calculate average offset
            offsets = [data["offset"] for data in self.time_sync_data.values()]
            avg_offset = sum(offsets) / len(offsets)
            
            # Send corrections to all students
            for roll, data in self.time_sync_data.items():
                correction = avg_offset - data["offset"]
                self.students[roll]["clock_offset"] = correction
                
                self._log_event("time_correction_sent", {
                    "roll": roll,
                    "correction": correction,
                    "avg_offset": avg_offset
                })
            
            self.last_sync_time = time.time()
            logger.info(f"Berkeley sync completed. Average offset: {avg_offset:.2f}s")
            
        except Exception as e:
            logger.error(f"Berkeley sync calculation error: {e}")
    
    # ===================== Question and Answer RPC APIs =====================
    def get_questions(self) -> Dict:
        """Return list of questions without revealing correct answers"""
        try:
            with self.lock:
                sanitized = [{"id": q["id"], "text": q["text"], "options": q["options"]} for q in self.questions]
                return {"success": True, "questions": sanitized}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_exam_timer(self) -> Dict:
        """Return remaining time and duration"""
        try:
            with self.lock:
                timer = None
                if self.exam_start_monotonic is not None and not self.exam_ended:
                    elapsed = time.monotonic() - self.exam_start_monotonic
                    remaining = max(0, int(self.exam_duration_seconds - elapsed))
                    timer = {"remaining_seconds": remaining, "duration_seconds": self.exam_duration_seconds}
                return {"success": True, "timer": timer}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def submit_answer(self, roll: str, question_id: int, answer: str, lamport_ts: int = None, mode: str = "autosave") -> Dict:
        """Submit or autosave an answer with eventual consistency semantics"""
        try:
            received_ts = lamport_ts if lamport_ts is not None else 0
            current_ts = self._increment_lamport_clock(received_ts)

            # Deadlock avoidance order: submit_lock -> answers_lock when final submission exists
            with self.answers_lock:
                if roll not in self.students:
                    return {"success": False, "message": "Invalid roll number"}

                # If final submission exists, reject autosave writes with older/equal Lamport ts
                final_meta = self.final_submissions.get(roll)
                if final_meta and mode == "autosave":
                    if received_ts is None or received_ts <= final_meta.get("lamport_ts", 0):
                        return {"success": False, "reason": "finalized", "message": "Final submission already recorded"}

                student_answers = self.answers.setdefault(roll, {})
                meta = student_answers.get(question_id, {"version": 0, "lamport_ts": -1, "value": None, "last_write_mode": None})

                # Eventual consistency: last-writer-wins by Lamport ts, tie-breaker by mode (final > autosave)
                should_write = False
                if current_ts > meta["lamport_ts"]:
                    should_write = True
                elif current_ts == meta["lamport_ts"]:
                    # Tie-break: final submit beats autosave
                    if mode == "final" and meta.get("last_write_mode") != "final":
                        should_write = True

                if should_write:
                    meta.update({
                        "value": answer,
                        "lamport_ts": current_ts,
                        "version": meta["version"] + 1,
                        "last_write_mode": mode
                    })
                    student_answers[question_id] = meta
                    self.version_counter += 1
                    self._log_event("answer_saved", {"roll": roll, "qid": question_id, "mode": mode, "version": meta["version"], "lamport_ts": current_ts})
                    return {"success": True, "version": meta["version"], "lamport_ts": current_ts}
                else:
                    return {"success": False, "reason": "stale_write", "message": "Stale write ignored", "current_ts": meta["lamport_ts"]}

        except Exception as e:
            logger.error(f"Error submitting answer for {roll}: {e}")
            return {"success": False, "message": str(e)}
    
    def request_cs(self, roll: str, timestamp) -> Dict:
        """Request critical section access using Ricart-Agrawala algorithm"""
        try:
            with self.cs_lock:
                # Accept timestamp as string or int to avoid XML-RPC i4 limits
                try:
                    ts_int = int(timestamp)
                except Exception:
                    ts_int = 0
                lamport_ts = self._increment_lamport_clock(ts_int)
                
                if roll not in self.students:
                    return {"success": False, "message": "Invalid roll number"}
                
                # Add to request queue
                request = {
                    "roll": roll,
                    "timestamp": lamport_ts,
                    "request_time": time.time()
                }
                
                self.cs_queue.append(request)
                self.cs_queue.sort(key=lambda x: (x["timestamp"], x["roll"]))  # Sort by timestamp, then roll
                
                self.pending_requests[roll] = request
                self.received_replies = set()
                
                self._log_event("cs_request", {
                    "roll": roll,
                    "timestamp": lamport_ts,
                    "queue_length": len(self.cs_queue)
                })
                
                # Check if this request can be granted immediately
                if self._can_grant_cs(request):
                    return self._grant_cs(request)
                else:
                    return {"success": True, "message": "Request queued", "position": len(self.cs_queue)}
                
        except Exception as e:
            logger.error(f"Error requesting CS for {roll}: {e}")
            return {"success": False, "message": f"CS request failed: {str(e)}"}
    
    def reply_cs(self, roll: str, timestamp) -> Dict:
        """Reply to critical section request"""
        try:
            with self.cs_lock:
                try:
                    ts_int = int(timestamp)
                except Exception:
                    ts_int = 0
                self._increment_lamport_clock(ts_int)
                
                if roll in self.received_replies:
                    return {"success": False, "message": "Already replied"}
                
                self.received_replies.add(roll)
                
                self._log_event("cs_reply", {
                    "roll": roll,
                    "timestamp": timestamp
                })
                
                # Check if we can grant CS to the next in queue
                if self.cs_queue and self._can_grant_cs(self.cs_queue[0]):
                    return self._grant_cs(self.cs_queue[0])
                
                return {"success": True, "message": "Reply recorded"}
                
        except Exception as e:
            logger.error(f"Error replying to CS for {roll}: {e}")
            return {"success": False, "message": f"CS reply failed: {str(e)}"}
    
    def _can_grant_cs(self, request: Dict) -> bool:
        """Check if critical section can be granted to a request"""
        if self.cs_holder is not None:
            return False
        
        # Check if we have replies from all other processes
        other_rolls = [r["roll"] for r in self.cs_queue if r["roll"] != request["roll"]]
        return all(roll in self.received_replies for roll in other_rolls)
    
    def _grant_cs(self, request: Dict) -> Dict:
        """Grant critical section access"""
        self.cs_holder = request["roll"]
        self.cs_queue.remove(request)
        
        if request["roll"] in self.pending_requests:
            del self.pending_requests[request["roll"]]
        
        self._log_event("cs_granted", {
            "roll": request["roll"],
            "timestamp": request["timestamp"]
        })
        
        return {
            "success": True,
            "message": "Critical section access granted",
            "holder": request["roll"]
        }
    
    def release_cs(self, roll: str) -> Dict:
        """Release critical section access"""
        try:
            with self.cs_lock:
                if self.cs_holder != roll:
                    return {"success": False, "message": "Not the current holder"}
                
                self.cs_holder = None
                self.received_replies.clear()
                
                self._log_event("cs_released", {"roll": roll})
                
                # Check if next request can be granted
                if self.cs_queue:
                    next_request = self.cs_queue[0]
                    if self._can_grant_cs(next_request):
                        return self._grant_cs(next_request)
                
                return {"success": True, "message": "Critical section released"}
                
        except Exception as e:
            logger.error(f"Error releasing CS for {roll}: {e}")
            return {"success": False, "message": f"CS release failed: {str(e)}"}
    
    def get_status(self, roll: str = None) -> Dict:
        """Get status of a specific student or all students"""
        try:
            with self.lock:
                if roll:
                    if roll not in self.students:
                        return {"success": False, "message": "Invalid roll number"}
                    timer = None
                    if self.exam_start_monotonic is not None and not self.exam_ended:
                        elapsed = time.monotonic() - self.exam_start_monotonic
                        remaining = max(0, int(self.exam_duration_seconds - elapsed))
                        timer = {"remaining_seconds": remaining, "duration_seconds": self.exam_duration_seconds}
                    return {
                        "success": True,
                        "student": self.students[roll].copy(),
                        "cs_holder": self.cs_holder,
                        "exam_started": self.exam_started,
                        "exam_ended": self.exam_ended,
                        "timer": timer
                    }
                else:
                    timer = None
                    if self.exam_start_monotonic is not None and not self.exam_ended:
                        elapsed = time.monotonic() - self.exam_start_monotonic
                        remaining = max(0, int(self.exam_duration_seconds - elapsed))
                        timer = {"remaining_seconds": remaining, "duration_seconds": self.exam_duration_seconds}
                    return {
                        "success": True,
                        "students": {k: v.copy() for k, v in self.students.items()},
                        "cs_holder": self.cs_holder,
                        "exam_started": self.exam_started,
                        "exam_ended": self.exam_ended,
                        "total_students": len(self.students),
                        "timer": timer
                    }
                    
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"success": False, "message": f"Status retrieval failed: {str(e)}"}
    
    def end_exam(self) -> Dict:
        """End the exam for all students"""
        try:
            with self.lock:
                if not self.exam_started:
                    return {"success": False, "message": "Exam not started"}
                
                self.exam_ended = True
                self.exam_started = False
                self.exam_start_monotonic = None
                
                # Auto-submit remaining students
                for roll, student in self.students.items():
                    if student["status"] == "in_progress":
                        student["status"] = "submitted"
                        student["submission_mode"] = "auto"
                        student["last_activity"] = time.time()
                
                self._log_event("exam_ended", {"total_students": len(self.students)})
                
                return {"success": True, "message": "Exam ended successfully"}
                
        except Exception as e:
            logger.error(f"Error ending exam: {e}")
            return {"success": False, "message": f"Failed to end exam: {str(e)}"}

def create_server(port: int = 8000, replica_id: str = "master"):
    """Create and start the XML-RPC server"""
    coordinator = ExamCoordinator(port, replica_id)
    
    try:
        server = SimpleXMLRPCServer(("0.0.0.0", port), allow_none=True)
        server.register_introspection_functions()
        
        # Register all methods
        server.register_function(coordinator.register_student, "register_student")
        server.register_function(coordinator.start_exam, "start_exam")
        server.register_function(coordinator.cheating, "cheating")
        server.register_function(coordinator.submit_exam, "submit_exam")
        server.register_function(coordinator.report_time, "report_time")
        server.register_function(coordinator.request_cs, "request_cs")
        server.register_function(coordinator.reply_cs, "reply_cs")
        server.register_function(coordinator.get_status, "get_status")
        server.register_function(coordinator.end_exam, "end_exam")
        server.register_function(coordinator.release_cs, "release_cs")
        # New RPC APIs
        server.register_function(coordinator.get_questions, "get_questions")
        server.register_function(coordinator.get_exam_timer, "get_exam_timer")
        server.register_function(coordinator.submit_answer, "submit_answer")
        
        logger.info(f"XML-RPC Server starting on port {port} (Replica: {replica_id})")
        return server, coordinator
    except Exception as e:
        logger.error(f"Failed to create server on port {port}: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    replica_id = sys.argv[2] if len(sys.argv) > 2 else "master"
    
    try:
        server, coordinator = create_server(port, replica_id)
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
            server.shutdown()
        except Exception as e:
            logger.error(f"Server error: {e}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
