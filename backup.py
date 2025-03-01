"""
Backup and restore functionality for Docker Compose services.
"""

import os
import json
import shutil
import tarfile
from datetime import datetime
from typing import Dict, Optional

class ServiceBackup:
    """Handle backup and restore of service data."""
    
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.backup_path = os.path.join(base_path, 'backups')
        os.makedirs(self.backup_path, exist_ok=True)

    def create_backup(self, service_id: str, compose_path: str) -> Optional[str]:
        """
        Create a backup of a service's compose files and volumes.
        
        Returns:
            Optional[str]: Path to backup file if successful, None otherwise
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{service_id}_{timestamp}.tar.gz"
            backup_file = os.path.join(self.backup_path, backup_name)
            
            with tarfile.open(backup_file, "w:gz") as tar:
                # Add compose directory
                tar.add(compose_path, arcname=os.path.basename(compose_path))
                
                # Add metadata
                metadata = {
                    "service_id": service_id,
                    "timestamp": timestamp,
                    "compose_path": compose_path
                }
                
                metadata_file = os.path.join(self.backup_path, "metadata.json")
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f)
                tar.add(metadata_file, arcname="metadata.json")
                os.remove(metadata_file)
            
            return backup_file
        except Exception as e:
            print(f"Backup failed: {str(e)}")
            return None

    def restore_backup(self, backup_file: str) -> Optional[Dict]:
        """
        Restore a service from backup.
        
        Returns:
            Optional[Dict]: Restored service metadata if successful, None otherwise
        """
        try:
            # Create temporary directory for restoration
            temp_dir = os.path.join(self.backup_path, 'temp_restore')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Extract backup
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(temp_dir)
            
            # Read metadata
            with open(os.path.join(temp_dir, "metadata.json")) as f:
                metadata = json.load(f)
            
            # Restore compose files
            service_dir = os.path.join(temp_dir, os.path.basename(metadata["compose_path"]))
            target_dir = metadata["compose_path"]
            
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.copytree(service_dir, target_dir)
            
            # Cleanup
            shutil.rmtree(temp_dir)
            
            return metadata
        except Exception as e:
            print(f"Restore failed: {str(e)}")
            return None
