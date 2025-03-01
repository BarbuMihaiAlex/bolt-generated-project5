"""
CTFd plugin for Docker Compose based challenges.
"""

from flask import Flask
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES

from .container_challenge import ContainerChallenge
from .setup import setup_default_configs
from .routes import register_app
from .logs import init_logs

def load(app: Flask) -> None:
    """
    Load the Docker Compose plugin into CTFd.
    """
    # Disable Flask-RESTX's automatic 404 help messages
    app.config['RESTX_ERROR_404_HELP'] = False
    
    # Create database tables
    app.db.create_all()
    
    # Setup default configurations
    setup_default_configs()
    
    # Register the container challenge type
    CHALLENGE_CLASSES["container"] = ContainerChallenge
    
    # Register plugin assets
    register_plugin_assets_directory(
        app, 
        base_path="/plugins/containers/assets/"
    )
    
    # Initialize logging
    init_logs(app)
    
    # Register routes
    containers_bp = register_app(app)
    app.register_blueprint(containers_bp)

    # Create default Docker network if it doesn't exist
    from .models import ContainerSettingsModel
    settings = {s.key: s.value for s in ContainerSettingsModel.query.all()}
    default_network = settings.get('compose_networks_default', 'ctfd_challenges')
    
    try:
        docker_client = app.container_manager.client
        if docker_client:
            networks = docker_client.networks.list(names=[default_network])
            if not networks:
                docker_client.networks.create(
                    default_network,
                    driver="bridge",
                    labels={"created_by": "ctfd_containers_plugin"}
                )
    except Exception as e:
        app.logger.error(f"Failed to create default network: {str(e)}")
