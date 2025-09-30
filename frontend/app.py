#!/usr/bin/env python3
"""
Online Exam Proctoring System - Flask Frontend
Provides web UI for teachers and students
"""

import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
import xmlrpc.client

app = Flask(__name__)

# Configuration
SERVER_URL = "http://127.0.0.1:8010"
LOAD_BALANCER_URL = "http://127.0.0.1:9010"

# Global state
current_server = None
server_proxy = None
load_balancer_proxy = None

def get_server_proxy():
    """Get server proxy (direct or through load balancer)"""
    global server_proxy, load_balancer_proxy
    
    if current_server == "load_balancer":
        if not load_balancer_proxy:
            load_balancer_proxy = xmlrpc.client.ServerProxy(LOAD_BALANCER_URL, allow_none=True)
        return load_balancer_proxy
    else:
        if not server_proxy:
            server_proxy = xmlrpc.client.ServerProxy(SERVER_URL, allow_none=True)
        return server_proxy

def rpc_call(method: str, *args):
    """Call RPC either directly or via load balancer invoke()"""
    proxy = get_server_proxy()
    if current_server == "load_balancer":
        return proxy.invoke(method, *args)
    func = getattr(proxy, method)
    return func(*args)

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')

@app.route('/teacher')
def teacher_dashboard():
    """Teacher dashboard"""
    return render_template('teacher.html')

@app.route('/student')
def student_dashboard():
    """Student dashboard"""
    return render_template('student.html')

@app.route('/api/register_student', methods=['POST'])
def api_register_student():
    """Register a new student"""
    try:
        data = request.get_json()
        roll = data.get('roll')
        
        if not roll:
            return jsonify({"success": False, "message": "Roll number required"})
        
        result = rpc_call('register_student', roll)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/start_exam', methods=['POST'])
def api_start_exam():
    """Start the exam"""
    try:
        result = rpc_call('start_exam')
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/end_exam', methods=['POST'])
def api_end_exam():
    """End the exam"""
    try:
        result = rpc_call('end_exam')
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/get_status')
def api_get_status():
    """Get exam status"""
    try:
        roll = request.args.get('roll')
        if roll:
            result = rpc_call('get_status', roll)
        else:
            result = rpc_call('get_status')
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/cheating', methods=['POST'])
def api_cheating():
    """Report cheating"""
    try:
        data = request.get_json()
        roll = data.get('roll')
        evidence = data.get('evidence', 'suspicious_activity')
        
        if not roll:
            return jsonify({"success": False, "message": "Roll number required"})
        
        result = rpc_call('cheating', roll, evidence)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/submit_exam', methods=['POST'])
def api_submit_exam():
    """Submit exam"""
    try:
        data = request.get_json()
        roll = data.get('roll')
        mode = data.get('mode', 'manual')
        
        if not roll:
            return jsonify({"success": False, "message": "Roll number required"})
        
        result = rpc_call('submit_exam', roll, mode)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/get_questions')
def api_get_questions():
    """Fetch questions for the exam"""
    try:
        result = rpc_call('get_questions')
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/get_timer')
def api_get_timer():
    """Fetch exam timer info"""
    try:
        result = rpc_call('get_exam_timer')
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/submit_answer', methods=['POST'])
def api_submit_answer():
    """Submit or autosave an answer"""
    try:
        data = request.get_json()
        roll = data.get('roll')
        question_id = data.get('question_id')
        answer = data.get('answer')
        mode = data.get('mode', 'autosave')
        lamport_ts = data.get('lamport_ts')
        
        if not roll or question_id is None or answer is None:
            return jsonify({"success": False, "message": "roll, question_id, answer required"})
        
        result = rpc_call('submit_answer', roll, int(question_id), answer, lamport_ts, mode)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/request_cs', methods=['POST'])
def api_request_cs():
    """Request critical section access"""
    try:
        data = request.get_json()
        roll = data.get('roll')
        
        if not roll:
            return jsonify({"success": False, "message": "Roll number required"})
        
        # Send timestamp as string to avoid XML-RPC i4 limits
        result = rpc_call('request_cs', roll, str(int(time.time() * 1000)))
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/release_cs', methods=['POST'])
def api_release_cs():
    """Release critical section access"""
    try:
        data = request.get_json()
        roll = data.get('roll')
        
        if not roll:
            return jsonify({"success": False, "message": "Roll number required"})
        
        result = rpc_call('release_cs', roll)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/report_time', methods=['POST'])
def api_report_time():
    """Report time for Berkeley sync"""
    try:
        data = request.get_json()
        roll = data.get('roll')
        reported_time = data.get('reported_time', time.time())
        
        if not roll:
            return jsonify({"success": False, "message": "Roll number required"})
        
        result = rpc_call('report_time', roll, reported_time)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/switch_server', methods=['POST'])
def api_switch_server():
    """Switch between direct server and load balancer"""
    global current_server
    
    data = request.get_json()
    server_type = data.get('server_type', 'direct')
    
    if server_type == 'load_balancer':
        current_server = "load_balancer"
    else:
        current_server = "direct"
    
    return jsonify({"success": True, "message": f"Switched to {server_type} server"})

@app.route('/api/get_balancer_stats')
def api_get_balancer_stats():
    """Get load balancer statistics"""
    try:
        if current_server != "load_balancer":
            return jsonify({"success": False, "message": "Load balancer not active"})
        
        proxy = get_server_proxy()
        result = proxy.get_stats()
        return jsonify({"success": True, "stats": result})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/events')
def api_events():
    """Server-sent events for real-time updates"""
    def event_stream():
        while True:
            try:
                proxy = get_server_proxy()
                result = proxy.get_status()
                
                if result.get("success"):
                    data = {
                        "timestamp": datetime.now().isoformat(),
                        "students": result.get("students", {}),
                        "exam_started": result.get("exam_started", False),
                        "exam_ended": result.get("exam_ended", False),
                        "cs_holder": result.get("cs_holder")
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                
                time.sleep(2)  # Update every 2 seconds
                
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(5)
    
    return Response(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    # Initialize with direct server
    current_server = "direct"
    
    print("Starting Flask frontend...")
    print(f"Server URL: {SERVER_URL}")
    print(f"Load Balancer URL: {LOAD_BALANCER_URL}")
    
    # Try different ports if 5000 is occupied
    ports_to_try = [5001, 5002, 5003, 5004, 5005, 5000]  # Start with 5001 to avoid ControlCenter
    port = None
    
    for p in ports_to_try:
        try:
            print(f"Trying port {p}...")
            app.run(debug=True, host='0.0.0.0', port=p, use_reloader=False)
            port = p
            break
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"Port {p} is already in use, trying next port...")
                continue
            else:
                print(f"Error starting on port {p}: {e}")
                break
        except Exception as e:
            print(f"Unexpected error starting on port {p}: {e}")
            break
    
    if port:
        print(f"✓ Flask application started successfully on port {port}")
        print(f"Access the application at: http://localhost:{port}")
    else:
        print("✗ Failed to start Flask application on any available port")
        print("Please check if any other services are using ports 5000-5005")
