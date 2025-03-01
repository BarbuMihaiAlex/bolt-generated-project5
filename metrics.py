"""
Metrics collection for Docker Compose services.
"""

import time
from typing import Dict, List, Optional
from datetime import datetime
from CTFd.models import db

class MetricsModel(db.Model):
    """Database model for service metrics."""
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(db.String(512))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    cpu_usage = db.Column(db.Float)
    memory_usage = db.Column(db.Integer)
    network_rx = db.Column(db.Integer)
    network_tx = db.Column(db.Integer)

class MetricsCollector:
    """Collect and store metrics from Docker Compose services."""
    
    def __init__(self, container_manager):
        self.container_manager = container_manager

    def collect_container_metrics(self, container_id: str) -> Optional[Dict]:
        """Collect metrics for a specific container."""
        try:
            stats = self.container_manager.client.containers.get(container_id).stats(stream=False)
            
            # Calculate CPU usage percentage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_usage = (cpu_delta / system_delta) * 100.0
            
            # Get memory usage in MB
            memory_usage = stats["memory_stats"]["usage"] / (1024 * 1024)
            
            # Get network stats
            network_stats = stats["networks"]["eth0"]
            
            metrics = {
                "cpu_usage": round(cpu_usage, 2),
                "memory_usage": round(memory_usage, 2),
                "network_rx": network_stats["rx_bytes"],
                "network_tx": network_stats["tx_bytes"]
            }
            
            return metrics
        except Exception:
            return None

    def store_metrics(self, container_id: str, metrics: Dict) -> None:
        """Store collected metrics in the database."""
        if metrics:
            metric = MetricsModel(
                container_id=container_id,
                cpu_usage=metrics["cpu_usage"],
                memory_usage=metrics["memory_usage"],
                network_rx=metrics["network_rx"],
                network_tx=metrics["network_tx"]
            )
            db.session.add(metric)
            db.session.commit()

    def get_container_metrics(self, container_id: str, limit: int = 100) -> List[Dict]:
        """Retrieve stored metrics for a container."""
        metrics = MetricsModel.query\
            .filter_by(container_id=container_id)\
            .order_by(MetricsModel.timestamp.desc())\
            .limit(limit)\
            .all()
        
        return [{
            "timestamp": m.timestamp.isoformat(),
            "cpu_usage": m.cpu_usage,
            "memory_usage": m.memory_usage,
            "network_rx": m.network_rx,
            "network_tx": m.network_tx
        } for m in metrics]
