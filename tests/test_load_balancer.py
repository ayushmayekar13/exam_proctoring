#!/usr/bin/env python3
"""
Unit tests for the load balancer
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_balancer import LoadBalancer

class TestLoadBalancer(unittest.TestCase):
    """Test cases for LoadBalancer class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.backends = [
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8001",
            "http://127.0.0.1:8002"
        ]
        self.balancer = LoadBalancer(self.backends, port=9000)
    
    def test_initialization(self):
        """Test load balancer initialization"""
        self.assertEqual(self.balancer.backends, self.backends)
        self.assertEqual(self.balancer.port, 9000)
        self.assertEqual(len(self.balancer.backend_status), 3)
        self.assertEqual(len(self.balancer.request_count), 3)
        
        # All backends should be initially healthy
        for backend in self.backends:
            self.assertTrue(self.balancer.backend_status[backend])
            self.assertEqual(self.balancer.request_count[backend], 0)
    
    def test_get_next_backend(self):
        """Test round-robin backend selection"""
        # Test multiple selections
        selected_backends = []
        for _ in range(6):  # 2 full cycles
            backend = self.balancer._get_next_backend()
            selected_backends.append(backend)
        
        # Should cycle through backends
        expected_cycle = self.backends * 2
        self.assertEqual(selected_backends, expected_cycle)
        
        # Request counts should be incremented
        for backend in self.backends:
            self.assertEqual(self.balancer.request_count[backend], 2)
    
    @patch('xmlrpc.client.ServerProxy')
    def test_dispatch_success(self, mock_server_proxy):
        """Test successful request dispatch"""
        # Mock server proxy
        mock_proxy = Mock()
        mock_proxy.get_status.return_value = {"success": True, "data": "test"}
        mock_server_proxy.return_value = mock_proxy
        
        # Test dispatch
        result = self.balancer._dispatch("get_status", ())
        self.assertEqual(result, {"success": True, "data": "test"})
        mock_proxy.get_status.assert_called_once()
    
    @patch('xmlrpc.client.ServerProxy')
    def test_dispatch_failure_with_retry(self, mock_server_proxy):
        """Test request dispatch with failure and retry"""
        # Mock server proxy to fail first time, succeed second time
        mock_proxy1 = Mock()
        mock_proxy1.get_status.side_effect = Exception("Connection failed")
        
        mock_proxy2 = Mock()
        mock_proxy2.get_status.return_value = {"success": True, "data": "retry_success"}
        
        mock_server_proxy.side_effect = [mock_proxy1, mock_proxy2]
        
        # Test dispatch with retry
        result = self.balancer._dispatch("get_status", ())
        self.assertEqual(result, {"success": True, "data": "retry_success"})
        
        # First backend should be marked as unhealthy
        self.assertFalse(self.balancer.backend_status[self.backends[0]])
    
    @patch('xmlrpc.client.ServerProxy')
    def test_health_check(self, mock_server_proxy):
        """Test health check functionality"""
        # Mock healthy backend
        mock_proxy = Mock()
        mock_proxy.get_status.return_value = {"success": True}
        mock_server_proxy.return_value = mock_proxy
        
        # Test health check
        is_healthy = self.balancer._is_backend_healthy(self.backends[0])
        self.assertTrue(is_healthy)
        
        # Mock unhealthy backend
        mock_proxy.get_status.side_effect = Exception("Connection failed")
        is_healthy = self.balancer._is_backend_healthy(self.backends[0])
        self.assertFalse(is_healthy)
    
    def test_add_backend(self):
        """Test adding a new backend"""
        new_backend = "http://127.0.0.1:8003"
        self.balancer.add_backend(new_backend)
        
        self.assertIn(new_backend, self.balancer.backends)
        self.assertTrue(self.balancer.backend_status[new_backend])
        self.assertEqual(self.balancer.request_count[new_backend], 0)
    
    def test_remove_backend(self):
        """Test removing a backend"""
        backend_to_remove = self.backends[0]
        self.balancer.remove_backend(backend_to_remove)
        
        self.assertNotIn(backend_to_remove, self.balancer.backends)
        self.assertNotIn(backend_to_remove, self.balancer.backend_status)
        self.assertNotIn(backend_to_remove, self.balancer.request_count)
    
    def test_get_stats(self):
        """Test statistics retrieval"""
        # Make some requests to update counts
        for _ in range(5):
            self.balancer._get_next_backend()
        
        stats = self.balancer.get_stats()
        
        self.assertEqual(stats["backends"], self.backends)
        self.assertEqual(stats["total_requests"], 5)
        self.assertIn("backend_status", stats)
        self.assertIn("request_count", stats)
    
    def test_all_backends_unhealthy(self):
        """Test behavior when all backends are unhealthy"""
        # Mark all backends as unhealthy
        for backend in self.backends:
            self.balancer.backend_status[backend] = False
        
        # Should still return a backend (first one)
        backend = self.balancer._get_next_backend()
        self.assertEqual(backend, self.backends[0])
    
    def test_empty_backends_list(self):
        """Test behavior with empty backends list"""
        empty_balancer = LoadBalancer([], port=9000)
        backend = empty_balancer._get_next_backend()
        self.assertIsNone(backend)

class TestLoadBalancerIntegration(unittest.TestCase):
    """Integration tests for load balancer"""
    
    def test_round_robin_distribution(self):
        """Test that requests are distributed evenly"""
        backends = ["http://127.0.0.1:8000", "http://127.0.0.1:8001"]
        balancer = LoadBalancer(backends)
        
        # Make many requests
        request_count = 100
        for _ in range(request_count):
            balancer._get_next_backend()
        
        # Each backend should have received approximately half the requests
        for backend in backends:
            count = balancer.request_count[backend]
            self.assertAlmostEqual(count, request_count // 2, delta=1)
    
    def test_backend_failover(self):
        """Test failover when backend becomes unhealthy"""
        backends = ["http://127.0.0.1:8000", "http://127.0.0.1:8001"]
        balancer = LoadBalancer(backends)
        
        # Mark first backend as unhealthy
        balancer.backend_status[backends[0]] = False
        
        # All requests should go to second backend
        for _ in range(10):
            backend = balancer._get_next_backend()
            self.assertEqual(backend, backends[1])
    
    def test_backend_recovery(self):
        """Test backend recovery after being marked unhealthy"""
        backends = ["http://127.0.0.1:8000", "http://127.0.0.1:8001"]
        balancer = LoadBalancer(backends)
        
        # Mark first backend as unhealthy
        balancer.backend_status[backends[0]] = False
        
        # All requests should go to second backend
        for _ in range(5):
            backend = balancer._get_next_backend()
            self.assertEqual(backend, backends[1])
        
        # Mark first backend as healthy again
        balancer.backend_status[backends[0]] = True
        
        # Requests should now be distributed again
        selected_backends = []
        for _ in range(4):
            backend = balancer._get_next_backend()
            selected_backends.append(backend)
        
        # Should see both backends
        self.assertIn(backends[0], selected_backends)
        self.assertIn(backends[1], selected_backends)

if __name__ == "__main__":
    unittest.main()

