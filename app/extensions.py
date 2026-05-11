from flask_login import LoginManager
from flask_mail import Mail
from celery import Celery

# Create the extension instances in a central place
login_manager = LoginManager()
mail = Mail()
celery = Celery(__name__)