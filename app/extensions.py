from flask_login import LoginManager
from flask_mail import Mail
# from celery import Celery  # REMOVED - Commented out for Render

# Initialize extensions WITHOUT Celery
login_manager = LoginManager()
mail = Mail()
# celery = Celery(__name__)  # REMOVED - Commented out for Render