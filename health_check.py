"""
Health check system for Docker Compose services.
"""

import time
import socket
import requests
from typing import Dict, Optional, Tuple

class HealthCheck:
    """
    Health check implementation for Docker Compose services.
    """
    @staticmethod
    def check_tcp_port(host: str, port: int, timeout: int = 5) -> bool:
        """Check if a TCP port is responding."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, socket.error):
            return False

    @staticmethod
    def check_http_endpoint(url: str, timeout: int = 5) -> bool:
        """Check if an HTTP endpoint is responding."""
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code < 500
        except requests.RequestException:
            return False

    @staticmethod
    def wait_for_service(
        host: str,
        port: int,
        protocol: str = 'tcp',
        max_retries: int = 30,
        delay: int = 1
    ) -> Tuple[bool, str]:
        """
        Wait for a service to become available.
        
        Args:
            host: Service hostname
            port: Service port
            protocol: 'tcp' or 'http'
            max_retries: Maximum number of retry attempts
            delay: Delay between retries in seconds
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        for attempt in range(max_retries):
            if protocol == 'tcp':
                if HealthCheck.check_tcp_port(host, port):
                    return True, "Service is ready"
            elif protocol == 'http':
                url = f"http://{host}:{port}"
                if HealthCheck.check_http_endpoint(url):
                    return True, "Service is ready"
            
            if attempt < max_retries - 1:
                time.sleep(delay)
        
        return False, "Service failed to become ready"
