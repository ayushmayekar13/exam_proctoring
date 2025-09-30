#!/usr/bin/env python3
"""
Online Exam Proctoring System - Load Balancer
Implements least-connections load balancing for multiple server replicas
"""

import itertools
import threading
import logging
import time
from typing import List, Dict, Optional
from xmlrpc.server import SimpleXMLRPCServer
import xmlrpc.client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LoadBalancer:
    """Least-connections load balancer for exam coordinator replicas"""
    
    def __init__(self, backends: List[str], port: int = 9010):
        self.backends = backends
        self.port = port
        self.lock = threading.Lock()
        self.backend_status = {backend: True for backend in backends}
        self.request_count = {backend: 0 for backend in backends}
        self.inflight = {backend: 0 for backend in backends}
        
        # Health check settings
        self.health_check_interval = 30  # seconds
        self.health_check_timeout = 5  # seconds
        
        logger.info(f"Load balancer initialized with {len(backends)} backends")
        logger.info(f"Backends: {backends}")
    
    def _is_backend_healthy(self, backend: str) -> bool:
        """Check if a backend is healthy"""
        try:
            proxy = xmlrpc.client.ServerProxy(backend, allow_none=True)
            # Simple health check - try to get status
            result = proxy.get_status()
            return result.get("success", False)
        except Exception as e:
            logger.warning(f"Health check failed for {backend}: {e}")
            return False
    
    def _health_check_worker(self):
        """Background health check worker"""
        while True:
            try:
                with self.lock:
                    for backend in self.backends:
                        is_healthy = self._is_backend_healthy(backend)
                        self.backend_status[backend] = is_healthy
                        
                        if is_healthy:
                            logger.debug(f"Backend {backend} is healthy")
                        else:
                            logger.warning(f"Backend {backend} is unhealthy")
                
                time.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Health check worker error: {e}")
                time.sleep(5)
    
    def _get_next_backend(self) -> Optional[str]:
        """Select healthy backend with least in-flight requests"""
        with self.lock:
            healthy_backends = [b for b in self.backends if self.backend_status.get(b, False)]
            if not healthy_backends:
                logger.error("No healthy backends available!")
                return self.backends[0] if self.backends else None

            # Choose backend with minimal in-flight; tie-breaker: lowest total request_count
            backend = min(
                healthy_backends,
                key=lambda b: (self.inflight.get(b, 0), self.request_count.get(b, 0), b)
            )
            self.request_count[backend] += 1
            self.inflight[backend] += 1
            return backend
    
    def _dispatch(self, method: str, params: tuple) -> any:
        """Dispatch request to appropriate backend"""
        backend = self._get_next_backend()
        
        if not backend:
            raise Exception("No backends available")
        
        try:
            proxy = xmlrpc.client.ServerProxy(backend, allow_none=True)
            func = getattr(proxy, method)
            result = func(*params)
            
            logger.debug(f"Request {method} dispatched to {backend}")
            return result
            
        except Exception as e:
            logger.error(f"Backend {backend} failed for method {method}: {e}")
            
            # Mark backend as unhealthy and retry with next one
            with self.lock:
                self.backend_status[backend] = False
                # Decrement inflight for failed backend
                if backend in self.inflight and self.inflight[backend] > 0:
                    self.inflight[backend] -= 1

            # Try next backend
            next_backend = self._get_next_backend()
            if next_backend and next_backend != backend:
                try:
                    proxy = xmlrpc.client.ServerProxy(next_backend, allow_none=True)
                    func = getattr(proxy, method)
                    result = func(*params)
                    logger.info(f"Request {method} retried on {next_backend}")
                    return result
                except Exception as retry_e:
                    logger.error(f"Retry also failed on {next_backend}: {retry_e}")
            
            raise Exception(f"All backends failed for method {method}: {e}")
        finally:
            # Always decrement inflight for the chosen backend
            with self.lock:
                if backend in self.inflight and self.inflight[backend] > 0:
                    self.inflight[backend] -= 1

    # Public RPC method to allow generic forwarding from clients
    def invoke(self, method: str, *params):
        """Invoke a backend RPC by method name with params"""
        return self._dispatch(method, params)
    
    def get_stats(self) -> Dict:
        """Get load balancer statistics"""
        with self.lock:
            return {
                "backends": self.backends,
                "backend_status": self.backend_status.copy(),
                "request_count": self.request_count.copy(),
                "total_requests": sum(self.request_count.values())
            }
    
    def add_backend(self, backend: str):
        """Add a new backend to the pool"""
        with self.lock:
            if backend not in self.backends:
                self.backends.append(backend)
                self.backend_status[backend] = True
                self.request_count[backend] = 0
                self.inflight[backend] = 0
                logger.info(f"Added backend: {backend}")
    
    def remove_backend(self, backend: str):
        """Remove a backend from the pool"""
        with self.lock:
            if backend in self.backends:
                self.backends.remove(backend)
                self.backend_status.pop(backend, None)
                self.request_count.pop(backend, None)
                self.inflight.pop(backend, None)
                logger.info(f"Removed backend: {backend}")

def create_load_balancer(backends: List[str], port: int = 9000):
    """Create and start the load balancer server"""
    balancer = LoadBalancer(backends, port)
    
    # Start health check worker
    health_thread = threading.Thread(target=balancer._health_check_worker, daemon=True)
    health_thread.start()
    
    # Create XML-RPC server
    server = SimpleXMLRPCServer(("0.0.0.0", port), allow_none=True)
    server.register_introspection_functions()
    server.register_instance(balancer)
    
    # Register additional utility methods
    server.register_function(balancer.get_stats, "get_stats")
    server.register_function(balancer.add_backend, "add_backend")
    server.register_function(balancer.remove_backend, "remove_backend")
    server.register_function(balancer.invoke, "invoke")
    
    logger.info(f"Load balancer starting on port {port}")
    return server, balancer

if __name__ == "__main__":
    import sys
    
    # Default backends
    default_backends = [
        "http://127.0.0.1:8000",  # Master server
        "http://127.0.0.1:8001",  # Replica 1
        "http://127.0.0.1:8002",  # Replica 2
    ]
    
    # Parse command line arguments
    port = 9000
    backends = default_backends
    
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    if len(sys.argv) > 2:
        backends = sys.argv[2].split(',')
    
    logger.info(f"Starting load balancer on port {port}")
    logger.info(f"Backends: {backends}")
    
    server, balancer = create_load_balancer(backends, port)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Load balancer shutting down...")
        server.shutdown()

