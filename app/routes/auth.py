from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify,current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.utils.helpers import hash_password, verify_password, generate_reset_token
from app.utils.email_service import send_password_reset_email
from app.utils.validators import validate_email, validate_password
import mysql.connector
from datetime import datetime, timedelta
# from app.utils.activity_logger import log_activity
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirect based on user role
        if current_user.role == 'super_admin':
            return redirect(url_for('super_admin.dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'trainer':
            return redirect(url_for('trainer.dashboard'))
        elif current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        # Validate input
        if not email or not password:
            flash('Please provide both email and password', 'danger')
            return render_template('auth/login.html')
        
        if not validate_email(email):
            flash('Please enter a valid email address', 'danger')
            return render_template('auth/login.html')
        
        # Authenticate user
        user = User.validate_login(email, password)
        
        if user:
            login_user(user, remember=remember)
            
            # Log login activity
            # log_activity(user.user_id, 'login', 'users', user.user_id, 
            #             f"User logged in from IP: {request.remote_addr}")
            
            # Redirect based on role
            if user.role == 'super_admin':
                return redirect(url_for('super_admin.dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'trainer':
                return redirect(url_for('trainer.dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Log logout activity
    # log_activity(current_user.user_id, 'logout', 'users', current_user.user_id, 
    #             f"User logged out from IP: {request.remote_addr}")
    
    logout_user()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('auth.login'))



@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email or not validate_email(email):
            flash('Please enter a valid email address', 'danger')
            return render_template('auth/forgot_password.html')

        # Check if user exists
        user = User.get_by_email(email)

        if user:
            # Generate reset token
            reset_token = generate_reset_token()
            expires_at = datetime.now() + timedelta(hours=1)

            # Store token in database
            conn = current_app.get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO password_resets (user_id, reset_token, expires_at) VALUES (%s, %s, %s)",
                        (user.user_id, reset_token, expires_at)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()

                    # Send reset email
                    email_sent = send_password_reset_email(user.email, user.full_name, reset_token)
                    if email_sent:
                        flash('Password reset instructions have been sent to your email.', 'success')
                    else:
                        flash('Failed to send reset email. Please try again later.', 'danger')

                    return redirect(url_for('auth.login'))
                except Exception as err:
                    flash('An error occurred. Please try again later.', 'danger')
                    conn.rollback()
                    cursor.close()
                    conn.close()
                    return render_template('auth/forgot_password.html')
        # If user does not exist, show generic message (do NOT access user.email!)
        flash('If your email exists in our system, you will receive password reset instructions.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Validate token
    conn = current_app.get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM password_resets WHERE reset_token = %s AND is_used = FALSE AND expires_at > NOW()",
            (token,)
        )
        token_data = cursor.fetchone()
        
        if not token_data:
            cursor.close()
            conn.close()
            flash('Invalid or expired reset token', 'danger')
            return redirect(url_for('auth.forgot_password'))
        
        user_id = token_data['user_id']
        user = User.get(user_id)
        
        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return render_template('auth/reset_password.html', token=token)
            
            is_valid, message = validate_password(password)
            if not is_valid:
                flash(message, 'danger')
                return render_template('auth/reset_password.html', token=token)
            
            # Update password
            hashed_password = hash_password(password)
            if User.update_password(user_id, hashed_password):
                # Mark token as used
                cursor.execute(
                    "UPDATE password_resets SET is_used = TRUE WHERE reset_token = %s",
                    (token,)
                )
                conn.commit()
                
                # Log password reset activity
                log_activity(user_id, 'password_reset', 'users', user_id, 
                            "User reset their password")
                
                flash('Password has been reset successfully. Please login with your new password.', 'success')
                cursor.close()
                conn.close()
                return redirect(url_for('auth.login'))
            else:
                flash('Failed to reset password. Please try again later.', 'danger')
        
        cursor.close()
        conn.close()
        return render_template('auth/reset_password.html', token=token, user=user)
    
    flash('An error occurred. Please try again later.', 'danger')
    return redirect(url_for('auth.forgot_password'))






@auth_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    # --- Server-Side Validation ---
    if not all([current_password, new_password, confirm_password]):
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    user = User.get(current_user.user_id)
    # Use the User object's method to check the password
    if not user or not user.check_password(current_password):
        return jsonify({'success': False, 'message': 'Your current password is not correct.'}), 401
    
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New passwords do not match.'}), 400

    is_valid, message = validate_password(new_password)
    if not is_valid:
        return jsonify({'success': False, 'message': message}), 400

    # --- Update Password in Database ---
    try:
        # Use the User object's method to set the new password
        user.set_password(new_password) 

        conn = current_app.get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error.'}), 500
        
        cursor = conn.cursor()
        # Update the database with the new hash from the user object
        cursor.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (user.password_hash, current_user.user_id))
        conn.commit()
        
        log_activity(current_user.user_id, 'update', 'users', current_user.user_id, "User changed their password")
        
        return jsonify({'success': True, 'message': 'Password changed successfully!'})
    except Exception as e:
        print(f"Error updating password: {e}")
        # Make sure to handle rollback in case of error
        if conn and conn.is_connected():
            conn.rollback()
        return jsonify({'success': False, 'message': 'A server error occurred while updating your password.'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# _______________________________________________________________________________________
def log_activity(user_id, action, table_affected, record_id, description):
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO activity_logs (user_id, action, table_affected, record_id, old_values, new_values, ip_address) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, action, table_affected, record_id, '{}', '{}', request.remote_addr)
            )
            conn.commit()
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            print(f"Error logging activity: {err}")
            if conn:
                conn.rollback()
                cursor.close()
                conn.close()




