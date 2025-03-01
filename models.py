"""
Updated models to support Docker Compose configurations.
"""

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from CTFd.models import db, Challenges

class ContainerChallengeModel(Challenges):
    """
    Represents a Docker Compose based challenge in CTFd.
    """
    __mapper_args__ = {"polymorphic_identity": "container"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    
    # Base configuration
    image = db.Column(db.Text)  # Main service image
    port = db.Column(db.Integer)  # Main service port
    command = db.Column(db.Text, default="")
    volumes = db.Column(db.Text, default="")
    
    # Additional compose-specific fields
    compose_config = db.Column(db.Text, default="")  # Additional compose configuration
    environment = db.Column(db.Text, default="")  # Environment variables
    networks = db.Column(db.Text, default="")  # Network configuration
    
    # Challenge scoring
    initial = db.Column(db.Integer, default=0)
    minimum = db.Column(db.Integer, default=0)
    decay = db.Column(db.Integer, default=0)

    def __init__(self, *args, **kwargs):
        super(ContainerChallengeModel, self).__init__(**kwargs)
        self.value = kwargs["initial"]

class ContainerInfoModel(db.Model):
    """
    Represents information about a running Docker Compose service instance.
    """
    __mapper_args__ = {"polymorphic_identity": "container_info"}
    
    # Primary identifier for the compose service
    container_id = db.Column(db.String(512), primary_key=True)
    
    # Challenge and user/team relationships
    challenge_id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE")
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )
    team_id = db.Column(
        db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE")
    )
    
    # Service information
    port = db.Column(db.Integer)  # Exposed port
    compose_path = db.Column(db.Text)  # Path to compose file
    service_name = db.Column(db.Text)  # Name of main service
    
    # Timing information
    timestamp = db.Column(db.Integer)  # Creation time
    expires = db.Column(db.Integer)  # Expiration time
    
    # Relationships
    user = db.relationship("Users", foreign_keys=[user_id])
    team = db.relationship("Teams", foreign_keys=[team_id])
    challenge = db.relationship(ContainerChallengeModel, foreign_keys=[challenge_id])

class ContainerSettingsModel(db.Model):
    """
    Configuration settings for the Docker Compose plugin.
    """
    key = db.Column(db.String(512), primary_key=True)
    value = db.Column(db.Text)

    @classmethod
    def apply_default_config(cls, key, value):
        """Apply default configuration if not exists."""
        if not cls.query.filter_by(key=key).first():
            db.session.add(cls(key=key, value=value))
