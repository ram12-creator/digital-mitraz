from flask_login import LoginManager
from flask_mail import Mail

# Initialize extensions WITHOUT Celery
login_manager = LoginManager()
mail = Mail()
