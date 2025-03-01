"""
Modified ContainerManager to work with Docker Compose instead of individual containers.
"""

import atexit
import time
import json
import os
import yaml
from subprocess import run, PIPE
import docker
import paramiko.ssh_exception
import requests

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers import SchedulerNotRunningError

from CTFd.models import db
from .models import ContainerInfoModel

class ContainerException(Exception):
    """Custom exception class for container-related errors."""
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self) -> str:
        if self.message:
            return self.message
        else:
            return "Unknown Container Exception"

class ContainerManager:
    """
    Manages Docker Compose services for CTFd challenges.
    """
    def __init__(self, settings, app):
        self.settings = settings
        self.client = None
        self.app = app
        self.compose_path = "/tmp/ctfd_compose"  # Base path for compose files
        
        if settings.get("docker_base_url") is None or settings.get("docker_base_url") == "":
            return

        try:
            self.initialize_connection(settings, app)
            # Create base directory for compose files if it doesn't exist
            os.makedirs(self.compose_path, exist_ok=True)
        except ContainerException:
            print("Docker could not initialize or connect.")
            return

    def initialize_connection(self, settings, app):
        """Initialize Docker connection and setup expiration scheduler."""
        self.settings = settings
        self.app = app

        try:
            self.expiration_scheduler.shutdown()
        except (SchedulerNotRunningError, AttributeError):
            pass

        if settings.get("docker_base_url") is None:
            self.client = None
            return

        try:
            self.client = docker.DockerClient(base_url=settings.get("docker_base_url"))
        except Exception as e:
            self.client = None
            raise ContainerException(f"CTFd could not connect to Docker: {str(e)}")

        try:
            self.expiration_seconds = int(settings.get("container_expiration", 0)) * 60
        except (ValueError, AttributeError):
            self.expiration_seconds = 0

        if self.expiration_seconds > 0:
            self.expiration_scheduler = BackgroundScheduler()
            self.expiration_scheduler.add_job(
                func=self.kill_expired_containers,
                args=(app,),
                trigger="interval",
                seconds=5
            )
            self.expiration_scheduler.start()
            atexit.register(lambda: self.expiration_scheduler.shutdown())

    def create_compose_file(self, challenge_id, image, port, command=None, volumes=None):
        """
        Create a docker-compose.yml file for a challenge.
        
        Args:
            challenge_id: Unique identifier for the challenge
            image: Docker image to use
            port: Port to expose
            command: Optional command to run
            volumes: Optional volume mappings
        """
        service_name = f"challenge_{challenge_id}"
        compose_dir = os.path.join(self.compose_path, service_name)
        os.makedirs(compose_dir, exist_ok=True)

        compose_config = {
            'version': '3',
            'services': {
                service_name: {
                    'image': image,
                    'ports': [f"{port}:{port}"],
                }
            }
        }

        if command:
            compose_config['services'][service_name]['command'] = command

        if volumes:
            compose_config['services'][service_name]['volumes'] = volumes

        # Add resource limits if configured
        if self.settings.get("container_maxmemory"):
            try:
                mem_limit = int(self.settings.get("container_maxmemory"))
                if mem_limit > 0:
                    compose_config['services'][service_name]['deploy'] = {
                        'resources': {
                            'limits': {
                                'memory': f"{mem_limit}m"
                            }
                        }
                    }
            except ValueError:
                raise ContainerException("Invalid memory limit configuration")

        if self.settings.get("container_maxcpu"):
            try:
                cpu_limit = float(self.settings.get("container_maxcpu"))
                if cpu_limit > 0:
                    if 'deploy' not in compose_config['services'][service_name]:
                        compose_config['services'][service_name]['deploy'] = {'resources': {'limits': {}}}
                    compose_config['services'][service_name]['deploy']['resources']['limits']['cpus'] = str(cpu_limit)
            except ValueError:
                raise ContainerException("Invalid CPU limit configuration")

        compose_file = os.path.join(compose_dir, 'docker-compose.yml')
        with open(compose_file, 'w') as f:
            yaml.dump(compose_config, f)

        return compose_dir, service_name

    def run_compose_command(self, compose_dir, command):
        """
        Run a docker-compose command in the specified directory.
        
        Args:
            compose_dir: Directory containing docker-compose.yml
            command: Command to run (e.g., ['up', '-d'])
        """
        result = run(
            ['docker-compose'] + command,
            cwd=compose_dir,
            stdout=PIPE,
            stderr=PIPE,
            text=True
        )
        
        if result.returncode != 0:
            raise ContainerException(f"Docker Compose command failed: {result.stderr}")
        
        return result.stdout

    def create_container(self, image, port, command=None, volumes=None):
        """
        Create and start a new Docker Compose service.
        """
        # Generate a unique ID for the service
        service_id = str(int(time.time()))
        
        # Create compose file
        compose_dir, service_name = self.create_compose_file(
            service_id, image, port, command, volumes
        )

        try:
            # Start the service
            self.run_compose_command(compose_dir, ['up', '-d'])
            
            # Return a container-like object for compatibility
            return type('Container', (), {'id': service_name})
        except Exception as e:
            raise ContainerException(f"Failed to start compose service: {str(e)}")

    def kill_container(self, container_id):
        """
        Stop and remove a Docker Compose service.
        """
        compose_dir = os.path.join(self.compose_path, container_id)
        if os.path.exists(compose_dir):
            try:
                self.run_compose_command(compose_dir, ['down'])
                # Clean up compose directory
                import shutil
                shutil.rmtree(compose_dir)
            except Exception as e:
                raise ContainerException(f"Failed to stop compose service: {str(e)}")

    def is_container_running(self, container_id):
        """
        Check if a Docker Compose service is running.
        """
        compose_dir = os.path.join(self.compose_path, container_id)
        if not os.path.exists(compose_dir):
            return False

        try:
            output = self.run_compose_command(compose_dir, ['ps', '--quiet'])
            return bool(output.strip())
        except:
            return False

    def get_container_port(self, container_id):
        """
        Get the host port that a service's port is mapped to.
        """
        compose_dir = os.path.join(self.compose_path, container_id)
        if not os.path.exists(compose_dir):
            return None

        try:
            # Read the compose file to get the port mapping
            with open(os.path.join(compose_dir, 'docker-compose.yml')) as f:
                config = yaml.safe_load(f)
            
            # Get the first port mapping
            ports = config['services'][container_id]['ports'][0]
            return ports.split(':')[0]  # Return the host port
        except:
            return None

    def get_images(self):
        """
        Get a list of available Docker images.
        """
        try:
            images = self.client.images.list()
            return sorted([tag for image in images for tag in image.tags if tag])
        except:
            return []

    def kill_expired_containers(self, app):
        """
        Kill containers that have expired.
        """
        with app.app_context():
            containers = ContainerInfoModel.query.all()
            for container in containers:
                if container.expires - int(time.time()) < 0:
                    try:
                        self.kill_container(container.container_id)
                    except ContainerException:
                        print("Failed to kill expired container")
                    db.session.delete(container)
                    db.session.commit()

    def is_connected(self):
        """
        Check if Docker is connected.
        """
        try:
            return self.client is not None and self.client.ping()
        except:
            return False
