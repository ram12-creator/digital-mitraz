from flask import Blueprint, redirect, url_for

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Redirect to the auth login page as the main entry point
    return redirect(url_for('auth.login'))