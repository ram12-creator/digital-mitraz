# This file is the official entry point for the Celery worker.

from app import create_app

# Create the Flask app using your application factory.
# This is crucial because it loads all configurations, including the Celery settings.
flask_app = create_app()

# Import the celery instance that was configured inside the create_app factory.
from app.extensions import celery

# This line is important for Celery tasks to have access to the Flask app context.
celery.conf.update(flask_app.config)

# To make this file executable or discoverable by Celery, we can define app context.
# While the ContextTask class handles this for task execution, this ensures the app is
# fully initialized when Celery inspects the file.
with flask_app.app_context():
    pass