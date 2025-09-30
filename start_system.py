#!/usr/bin/env python3
"""
Online Exam Proctoring System - Startup Script
Convenient script to start all system components
"""

import subprocess
import time
import sys
import os
import signal
import threading
from pathlib import Path

class SystemManager:
    """Manages starting and stopping all system components"""
    
    def __init__(self):
        self.processes = []
        self.running = False
        
    def start_component(self, name, command_args, cwd=None, wait_time=0):
        """Start a system component using current Python interpreter"""
        try:
            print(f"Starting {name}...")
            # Build the command: [python_exe, script, ...args]
            if isinstance(command_args, (list, tuple)):
                args = [sys.executable] + list(command_args)
            else:
                parts = str(command_args).split()
                # If user accidentally provided leading 'python', drop it
                if parts and parts[0].lower() in ("python", "python3"):
                    parts = parts[1:]
                args = [sys.executable] + parts

            process = subprocess.Popen(
                args,
                cwd=cwd,
                stdout=None,  # inherit parent stdout
                stderr=None,  # inherit parent stderr
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            self.processes.append((name, process))
            print(f"✓ {name} started (PID: {process.pid})")
            
            # Wait for component to be ready
            if wait_time > 0:
                print(f"Waiting {wait_time} seconds for {name} to initialize...")
                time.sleep(wait_time)
            
            return process
        except Exception as e:
            print(f"✗ Failed to start {name}: {e}")
            return None
    
    def start_all(self):
        """Start all system components"""
        print("="*60)
        print("ONLINE EXAM PROCTORING SYSTEM - STARTUP")
        print("="*60)
        
        # Start main coordinator server
        self.start_component(
            "Main Coordinator Server",
            ["server.py", "8010", "master"],
            wait_time=0
        )
        
        # Start replica servers
        self.start_component(
            "Replica Server 1",
            ["server.py", "8011", "replica1"],
            wait_time=0
        )
        
        self.start_component(
            "Replica Server 2", 
            ["server.py", "8012", "replica2"],
            wait_time=0
        )
        
        # Start load balancer
        self.start_component(
            "Load Balancer",
            ["load_balancer.py", "9010", "http://127.0.0.1:8010,http://127.0.0.1:8011,http://127.0.0.1:8012"],
            wait_time=0
        )
        
        # Start Flask web interface
        self.start_component(
            "Flask Web Interface",
            ["app.py"],
            cwd="frontend",
            wait_time=0
        )

        # Health checks
        print("\nPerforming health checks...")
        servers_ok = self.wait_for_xmlrpc("http://127.0.0.1:8010", name="Main Coordinator Server")
        repl1_ok = self.wait_for_xmlrpc("http://127.0.0.1:8011", name="Replica Server 1")
        repl2_ok = self.wait_for_xmlrpc("http://127.0.0.1:8012", name="Replica Server 2")
        lb_ok = self.wait_for_balancer("http://127.0.0.1:9010")
        ui_ok = self.wait_for_http("http://127.0.0.1:5001") or self.wait_for_http("http://127.0.0.1:5000")
        
        self.running = True
        print("\n" + "="*60)
        print("SYSTEM STARTUP COMPLETE")
        print("="*60)
        print("Access the web interface at: http://localhost:5001 (or the printed port)")
        print("Teacher Dashboard: http://localhost:5000/teacher")
        print("Student Dashboard: http://localhost:5000/student")
        print("\nPress Ctrl+C to stop all components")
        print("="*60)
    
    def stop_all(self):
        """Stop all system components"""
        print("\n" + "="*60)
        print("STOPPING SYSTEM COMPONENTS")
        print("="*60)
        
        for name, process in self.processes:
            try:
                print(f"Stopping {name}...")
                if os.name == 'nt':
                    process.terminate()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
                print(f"✓ {name} stopped")
            except subprocess.TimeoutExpired:
                print(f"Force killing {name}...")
                if os.name == 'nt':
                    process.kill()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                print(f"✓ {name} force stopped")
            except Exception as e:
                print(f"✗ Error stopping {name}: {e}")
        
        self.running = False
        print("All components stopped")
        print("="*60)
    
    def check_service_health(self, url, name):
        """Check if a service is responding"""
        try:
            import xmlrpc.client
            proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
            result = proxy.get_status()
            return result.get("success", False)
        except:
            return False

    def wait_for_xmlrpc(self, url, name, retries=20, delay=0.5):
        """Wait until an XML-RPC endpoint is healthy"""
        for _ in range(retries):
            if self.check_service_health(url, name):
                print(f"✓ {name} is healthy at {url}")
                return True
            time.sleep(delay)
        print(f"✗ {name} not healthy at {url}")
        return False

    def wait_for_balancer(self, url, retries=20, delay=0.5):
        try:
            import xmlrpc.client
            proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
            for _ in range(retries):
                try:
                    proxy.get_stats()
                    print(f"✓ Load Balancer is healthy at {url}")
                    return True
                except Exception:
                    time.sleep(delay)
        except Exception:
            pass
        print(f"✗ Load Balancer not healthy at {url}")
        return False

    def wait_for_http(self, url, retries=40, delay=0.5):
        try:
            from urllib.request import urlopen
            for _ in range(retries):
                try:
                    with urlopen(url) as resp:
                        if resp.status in (200, 301, 302, 403):
                            print(f"✓ Web UI responding at {url} (status {resp.status})")
                            return True
                except Exception:
                    time.sleep(delay)
        except Exception:
            pass
        print(f"✗ Web UI not responding at {url}")
        return False
    
    def monitor_processes(self):
        """Monitor running processes"""
        while self.running:
            try:
                for name, process in self.processes:
                    if process.poll() is not None:
                        print(f"⚠ {name} has stopped unexpectedly")
                time.sleep(5)
            except KeyboardInterrupt:
                break
    
    def run_demo(self):
        """Run the demo simulation"""
        print("\n" + "="*60)
        print("RUNNING DEMO SIMULATION")
        print("="*60)
        
        # Wait for system to be ready
        print("Waiting for system to be ready...")
        time.sleep(5)
        
        # Run demo
        try:
            subprocess.run([sys.executable, "demo_simulation.py"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Demo failed: {e}")
        except KeyboardInterrupt:
            print("Demo interrupted")
    
    def run_tests(self):
        """Run the quick test script"""
        print("\n" + "="*60)
        print("RUNNING SYSTEM QUICK TESTS")
        print("="*60)
        
        # Wait for system to be ready
        print("Waiting for system to be ready...")
        time.sleep(5)
        
        # Run tests
        try:
            subprocess.run([sys.executable, "test_system.py"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Tests failed: {e}")
        except KeyboardInterrupt:
            print("Tests interrupted")

def signal_handler(signum, frame):
    """Handle interrupt signals"""
    print("\nReceived interrupt signal...")
    manager.stop_all()
    sys.exit(0)

def main():
    """Main function"""
    global manager
    manager = SystemManager()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check if we're in the right directory
    if not os.path.exists("server.py"):
        print("Error: Please run this script from the exam_proctoring_system directory")
        sys.exit(1)
    
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo = True
        run_tests = False
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_tests = True
        run_demo = False
    else:
        run_demo = False
        run_tests = False
    
    try:
        # Start all components
        manager.start_all()
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=manager.monitor_processes, daemon=True)
        monitor_thread.start()
        
        # Run demo or tests if requested
        if run_demo:
            manager.run_demo()
        elif run_tests:
            manager.run_tests()
        
        # Keep running until interrupted
        while manager.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop_all()

if __name__ == "__main__":
    main()
