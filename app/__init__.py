from flask import Flask
import mysql.connector
from dotenv import load_dotenv
import os
import urllib.parse

# Import the extension instances that were created globally
from .extensions import login_manager, mail

# Load environment variables from .env file
load_dotenv()

def create_app():
    """
    The Flask Application Factory.
    Creates, configures, and returns the Flask app.
    """
    app = Flask(__name__)

    # --- Load Configuration from .env ---
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        DEBUG=os.getenv('DEBUG', 'False').lower() in ['true', '1', 't'],
        DATABASE_URL=os.getenv('DATABASE_URL'),
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'},
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        # Mail Configuration for SendGrid
        MAIL_SERVER=os.getenv('MAIL_SERVER'),
        MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't'],
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER')
    )
    
    # Create necessary upload subdirectories if they don't exist
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'assignments'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'submissions'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)
    
    # --- Initialize Extensions with the App ---
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    mail.init_app(app)

    # --- Database Connection Helper using DATABASE_URL ---
    def get_db_connection():
        try:
            database_url = app.config['DATABASE_URL']
            
            # Parse the DATABASE_URL
            parsed = urllib.parse.urlparse(database_url)
            
            # Extract connection parameters
            config = {
                'host': parsed.hostname,
                'port': parsed.port,
                'user': parsed.username,
                'password': parsed.password,
                'database': parsed.path[1:] if parsed.path else 'defaultdb',
                'use_pure': True,
                'connection_timeout': 60,
                'ssl_disabled': False
            }
            
            # Remove any None values
            config = {k: v for k, v in config.items() if v is not None}
            
            app.logger.info(f"Connecting to {config['host']}:{config['port']}")
            
            # Create connection
            conn = mysql.connector.connect(**config)
            conn.cmd_reset_connection()
            
            app.logger.info("Database connection established successfully!")
            return conn
            
        except mysql.connector.Error as err:
            app.logger.error(f"Database connection error: {err}")
            app.logger.error(f"Error code: {err.errno}")
            if hasattr(err, 'msg'):
                app.logger.error(f"Error message: {err.msg}")
            return None
        except Exception as e:
            app.logger.error(f"Unexpected database error: {e}")
            return None
    
    app.get_db_connection = get_db_connection

    # --- Register Blueprints ---
    with app.app_context():
        from app.routes.auth import auth_bp
        from app.routes.super_admin import super_admin_bp
        from app.routes.admin import admin_bp
        from app.routes.trainer import trainer_bp
        from app.routes.student import student_bp
        from app.main import main_bp
        from app.utils.template_filters import filters_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(super_admin_bp, url_prefix='/super_admin')
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(trainer_bp, url_prefix='/trainer')
        app.register_blueprint(student_bp, url_prefix='/student')
        app.register_blueprint(main_bp)
        app.register_blueprint(filters_bp)

    return app