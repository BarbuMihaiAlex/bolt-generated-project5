"""
Helper functions for Docker Compose route handling.
"""

import time
import json
import datetime
import os
import yaml
from typing import Dict, Any, Tuple

from CTFd.models import db
from .logs import log
from .models import ContainerInfoModel, ContainerChallengeModel

def create_compose_service(container_manager, challenge_id: int, user_id: int, team_id: int, docker_assignment: str) -> Tuple[Dict[str, Any], int]:
    """
    Create a new Docker Compose service for a challenge.
    """
    log("containers_debug", format="Creating compose service for challenge {challenge_id}", 
        challenge_id=challenge_id)

    challenge = ContainerChallengeModel.query.filter_by(id=challenge_id).first()
    if not challenge:
        return {"error": "Challenge not found"}, 400

    # Check existing containers based on assignment type
    if docker_assignment in ["user", "unlimited"]:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge_id,
            user_id=user_id
        ).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge_id,
            team_id=team_id
        ).first()

    # Handle existing container
    if running_container:
        try:
            if container_manager.is_container_running(running_container.container_id):
                return {
                    "status": "already_running",
                    "hostname": challenge.connection_info,
                    "port": running_container.port,
                    "expires": running_container.expires
                }, 200
            else:
                db.session.delete(running_container)
                db.session.commit()
        except Exception as e:
            log("containers_errors", format="Error checking container status: {error}",
                error=str(e))
            return {"error": "Error checking container status"}, 500

    # Create new compose service
    try:
        # Parse additional compose configurations
        compose_config = json.loads(challenge.compose_config) if challenge.compose_config else {}
        environment = json.loads(challenge.environment) if challenge.environment else {}
        networks = json.loads(challenge.networks) if challenge.networks else {}

        # Create container with compose configuration
        created_service = container_manager.create_container(
            image=challenge.image,
            port=challenge.port,
            command=challenge.command,
            volumes=challenge.volumes,
            compose_config=compose_config,
            environment=environment,
            networks=networks
        )

        # Get assigned port
        port = container_manager.get_container_port(created_service.id)
        if not port:
            return {"error": "Could not get port assignment"}, 500

        # Calculate expiration
        expires = int(time.time() + container_manager.expiration_seconds)

        # Create database record
        new_container = ContainerInfoModel(
            container_id=created_service.id,
            challenge_id=challenge.id,
            user_id=user_id,
            team_id=team_id,
            port=port,
            compose_path=created_service.compose_path,
            service_name=created_service.service_name,
            timestamp=int(time.time()),
            expires=expires
        )

        db.session.add(new_container)
        db.session.commit()

        return {
            "status": "created",
            "hostname": challenge.connection_info,
            "port": port,
            "expires": expires
        }, 200

    except Exception as e:
        log("containers_errors", format="Error creating compose service: {error}",
            error=str(e))
        return {"error": f"Failed to create service: {str(e)}"}, 500

def kill_compose_service(container_manager, container_id: str, challenge_id: str) -> Tuple[Dict[str, Any], int]:
    """
    Kill a running Docker Compose service.
    """
    log("containers_debug", format="Killing compose service {container_id}",
        container_id=container_id)

    container = ContainerInfoModel.query.filter_by(container_id=container_id).first()
    if not container:
        return {"error": "Service not found"}, 400

    try:
        container_manager.kill_container(container_id)
        db.session.delete(container)
        db.session.commit()
        return {"success": "Service stopped and removed"}, 200
    except Exception as e:
        log("containers_errors", format="Error killing compose service: {error}",
            error=str(e))
        return {"error": f"Failed to stop service: {str(e)}"}, 500

def renew_compose_service(container_manager, challenge_id: int, user_id: int, team_id: int, docker_assignment: str) -> Tuple[Dict[str, Any], int]:
    """
    Renew the expiration time for a running compose service.
    """
    log("containers_debug", format="Renewing compose service for challenge {challenge_id}",
        challenge_id=challenge_id)

    # Get running container based on assignment type
    if docker_assignment in ["user", "unlimited"]:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge_id,
            user_id=user_id
        ).first()
    else:
        running_container = ContainerInfoModel.query.filter_by(
            challenge_id=challenge_id,
            team_id=team_id
        ).first()

    if not running_container:
        return {"error": "No running service found"}, 400

    try:
        # Update expiration time
        new_expiration = int(time.time() + container_manager.expiration_seconds)
        running_container.expires = new_expiration
        db.session.commit()

        return {"success": "Service renewed", "expires": new_expiration}, 200
    except Exception as e:
        log("containers_errors", format="Error renewing compose service: {error}",
            error=str(e))
        return {"error": f"Failed to renew service: {str(e)}"}, 500
