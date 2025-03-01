"""
Updated challenge type implementation for Docker Compose based challenges.
"""

from __future__ import division
import math
import json
from typing import Dict, Any, Optional

from flask import Request
from CTFd.models import db, Solves, Users, Teams
from CTFd.plugins.challenges import BaseChallenge
from CTFd.utils.modes import get_model

from .models import ContainerChallengeModel

class ContainerChallenge(BaseChallenge):
    """
    ContainerChallenge class for handling Docker Compose based challenges.
    """
    id = "container"
    name = "container"
    templates = {
        "create": "/plugins/containers/assets/create.html",
        "update": "/plugins/containers/assets/update.html",
        "view": "/plugins/containers/assets/view.html",
    }
    scripts = {
        "create": "/plugins/containers/assets/create.js",
        "update": "/plugins/containers/assets/update.js",
        "view": "/plugins/containers/assets/view.js",
    }
    route = "/plugins/containers/assets/"
    challenge_model = ContainerChallengeModel

    @classmethod
    def read(cls, challenge: ContainerChallengeModel) -> Dict[str, Any]:
        """
        Read challenge data for frontend processing.
        """
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "image": challenge.image,
            "port": challenge.port,
            "command": challenge.command,
            "initial": challenge.initial,
            "decay": challenge.decay,
            "minimum": challenge.minimum,
            "description": challenge.description,
            "connection_info": challenge.connection_info,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "type_data": {
                "id": cls.id,
                "name": cls.name,
                "templates": cls.templates,
                "scripts": cls.scripts,
            },
            "compose_config": challenge.compose_config,
            "environment": challenge.environment,
            "networks": challenge.networks,
        }
        return data

    @classmethod
    def update(cls, challenge: ContainerChallengeModel, request: Request) -> ContainerChallengeModel:
        """
        Update challenge with new data from request.
        """
        data = request.form or request.get_json()

        for attr, value in data.items():
            if attr in ("initial", "minimum", "decay"):
                value = float(value)
            elif attr in ("compose_config", "environment", "networks"):
                # Validate JSON format for compose-specific fields
                try:
                    if value:
                        json.loads(value)
                except json.JSONDecodeError:
                    continue
            setattr(challenge, attr, value)

        return cls.calculate_value(challenge)

    @classmethod
    def calculate_value(cls, challenge: ContainerChallengeModel) -> ContainerChallengeModel:
        """
        Calculate dynamic challenge value based on solves.
        """
        Model = get_model()

        solve_count = (
            Solves.query.join(Model, Solves.account_id == Model.id)
            .filter(
                Solves.challenge_id == challenge.id,
                Model.hidden == False,
                Model.banned == False,
            )
            .count()
        )

        # Account for the first solve
        if solve_count != 0:
            solve_count -= 1

        # Calculate dynamic value
        value = (
            ((challenge.minimum - challenge.initial) / (challenge.decay ** 2))
            * (solve_count ** 2)
        ) + challenge.initial

        value = math.ceil(value)

        # Ensure value doesn't go below minimum
        if value < challenge.minimum:
            value = challenge.minimum

        challenge.value = value
        db.session.commit()
        return challenge

    @classmethod
    def solve(cls, user: Users, team: Optional[Teams], challenge: ContainerChallengeModel, request: Request) -> None:
        """
        Handle challenge solve.
        """
        super().solve(user, team, challenge, request)
        cls.calculate_value(challenge)
