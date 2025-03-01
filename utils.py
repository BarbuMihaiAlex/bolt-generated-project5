"""
Utility functions for Docker Compose challenge management.
"""

import os
import yaml
import json
from typing import Dict, Any, Optional

def generate_compose_config(
    service_name: str,
    image: str,
    port: int,
    command: Optional[str] = None,
    volumes: Optional[str] = None,
    compose_config: Optional[str] = None,
    environment: Optional[str] = None,
    networks: Optional[str] = None,
    compose_version: str = "3",
    default_network: str = "ctfd_challenges"
) -> Dict[str, Any]:
    """
    Generate a Docker Compose configuration dictionary.
    """
    # Base service configuration
    service_config = {
        "image": image,
        "ports": [f"{port}:{port}"],
    }

    # Add command if specified
    if command:
        service_config["command"] = command

    # Add volumes if specified
    if volumes:
        try:
            volumes_dict = json.loads(volumes)
            service_config["volumes"] = volumes_dict
        except json.JSONDecodeError:
            pass

    # Add environment variables if specified
    if environment:
        try:
            env_dict = json.loads(environment)
            service_config["environment"] = env_dict
        except json.JSONDecodeError:
            pass

    # Base compose configuration
    compose_dict = {
        "version": compose_version,
        "services": {
            service_name: service_config
        },
        "networks": {
            default_network: {
                "external": True
            }
        }
    }

    # Add custom networks if specified
    if networks:
        try:
            networks_dict = json.loads(networks)
            for network_name, network_config in networks_dict.items():
                if network_config is None:
                    compose_dict["networks"][network_name] = {"external": True}
                else:
                    compose_dict["networks"][network_name] = network_config
            service_config["networks"] = list(networks_dict.keys()) + [default_network]
        except json.JSONDecodeError:
            pass

    # Merge additional compose configuration if specified
    if compose_config:
        try:
            additional_config = json.loads(compose_config)
            service_config.update(additional_config)
        except json.JSONDecodeError:
            pass

    return compose_dict

def write_compose_file(compose_dir: str, compose_config: Dict[str, Any]) -> str:
    """
    Write Docker Compose configuration to a file.
    """
    os.makedirs(compose_dir, exist_ok=True)
    compose_file = os.path.join(compose_dir, 'docker-compose.yml')
    
    with open(compose_file, 'w') as f:
        yaml.dump(compose_config, f, default_flow_style=False)
    
    return compose_file

def validate_compose_config(compose_config: Dict[str, Any]) -> bool:
    """
    Validate Docker Compose configuration.
    """
    required_fields = ['version', 'services']
    
    # Check required fields
    if not all(field in compose_config for field in required_fields):
        return False
    
    # Check services configuration
    services = compose_config.get('services', {})
    if not isinstance(services, dict) or not services:
        return False
    
    # Validate each service
    for service_name, service_config in services.items():
        if not isinstance(service_config, dict):
            return False
        if 'image' not in service_config:
            return False
    
    return True

def cleanup_compose_files(compose_dir: str) -> None:
    """
    Clean up Docker Compose files and directories.
    """
    try:
        import shutil
        shutil.rmtree(compose_dir)
    except Exception:
        pass
