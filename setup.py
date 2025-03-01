"""
Updated setup configuration for Docker Compose support.
"""

from .models import db, ContainerSettingsModel

def setup_default_configs():
    """
    Sets up default configurations for Docker Compose based containers.
    """
    default_configs = {
        "setup": "true",
        "docker_base_url": "unix://var/run/docker.sock",
        "docker_hostname": "",
        "container_expiration": "45",
        "container_maxmemory": "512",
        "container_maxcpu": "0.5",
        "docker_assignment": "user",
        "compose_version": "3",  # Docker Compose file version
        "compose_project_prefix": "ctfd",  # Prefix for compose project names
        "compose_networks_default": "ctfd_challenges",  # Default network for services
    }

    for key, val in default_configs.items():
        ContainerSettingsModel.apply_default_config(key, val)

    db.session.commit()
