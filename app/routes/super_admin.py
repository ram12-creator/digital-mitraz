from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models import User
from app.utils.helpers import generate_password, hash_password, get_course_stats
from app.utils.email_service import send_credentials_email
from app.utils.validators import validate_email, validate_phone, validate_date_range
import mysql.connector
from datetime import datetime
from collections import defaultdict 
import csv
import io
import os
from werkzeug.utils import secure_filename
import time
import json






# import pandas as pd
# import matplotlib
# matplotlib.use('Agg') # Set non-GUI backend
# import matplotlib.pyplot as plt
# import seaborn as sns
# import io
# import base64


super_admin_bp = Blueprint('super_admin', __name__)


# Add these configuration variables to your app config
# UPLOAD_FOLDER = 'app/static/uploads/profile_pictures'
# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']



@super_admin_bp.before_request
def restrict_to_super_admin():
    if not current_user.is_authenticated or current_user.role != 'super_admin':
        flash('Access denied. Super admin privileges required.', 'danger')
        return redirect(url_for('auth.login'))



def log_activity(user_id, action, table_affected, record_id, description):
    # This is a placeholder for your logging function. Ensure it exists and works.
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO activity_logs (user_id, action, table_affected, record_id, description, ip_address) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, action, table_affected, record_id, description, request.remote_addr)
            )
            conn.commit()
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

# --- CORRECTED AND ENHANCED DASHBOARD ROUTE ---
@super_admin_bp.route('/dashboard')
@login_required
def dashboard():
    conn = current_app.get_db_connection()
    stats = {
        'total_courses': 0, 'active_courses': 0, 'total_admins': 0,
        'total_trainers': 0, 'total_students': 0
    }
    # Initialize chart_data as an empty dictionary to prevent errors
    chart_data = {} 
    
    if not conn:
        flash('Database connection error.', 'danger')
        # CRITICAL FIX: Pass an empty chart_data object even on error
        return render_template('super_admin/dashboard.html', stats=stats, chart_data={})

    try:
        cursor = conn.cursor(dictionary=True)
        
        # --- 1. Fetch KPI Statistics (Same as before) ---
        cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN is_active = TRUE THEN 1 ELSE 0 END) as active FROM courses")
        course_data = cursor.fetchone()
        if course_data:
            stats['total_courses'] = course_data.get('total', 0)
            stats['active_courses'] = course_data.get('active', 0)

        cursor.execute("SELECT role, COUNT(*) as count FROM users WHERE role IN ('admin', 'trainer', 'student') GROUP BY role")
        role_data = cursor.fetchall()
        user_dist_labels = []
        user_dist_data = []
        for row in role_data:
            user_dist_labels.append(row['role'].title())
            user_dist_data.append(row['count'])
            if row['role'] == 'admin': stats['total_admins'] = row['count']
            elif row['role'] == 'trainer': stats['total_trainers'] = row['count']
            elif row['role'] == 'student': stats['total_students'] = row['count']
        
        # --- 2. Prepare Data for Charts ---

        # Chart 1: User Role Distribution (Pie Chart)
        chart_data['user_distribution'] = {
            'labels': user_dist_labels,
            'data': user_dist_data
        }
        
        # Chart 2: Course Popularity by Enrollment (Bar Chart)
        cursor.execute("""
            SELECT c.course_name, COUNT(s.student_id) as student_count
            FROM courses c
            LEFT JOIN students s ON c.course_id = s.course_id
            WHERE c.is_active = TRUE
            GROUP BY c.course_id, c.course_name
            ORDER BY student_count DESC
            LIMIT 7
        """)
        course_popularity = cursor.fetchall()
        chart_data['course_popularity'] = {
            'labels': [row['course_name'] for row in course_popularity],
            'data': [row['student_count'] for row in course_popularity]
        }
        
    except mysql.connector.Error as err:
        flash(f'Error retrieving dashboard data: {err}', 'danger')
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    
    # CRITICAL FIX: Pass the populated chart_data to the template
    return render_template('super_admin/dashboard.html', stats=stats, chart_data=chart_data)


# ____________________________________________________________________________





@super_admin_bp.route('/courses')
@login_required
def course_management():
    conn = current_app.get_db_connection()
    courses = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.*, u.full_name as created_by_name 
                FROM courses c 
                LEFT JOIN users u ON c.created_by = u.user_id 
                ORDER BY c.created_at DESC
            """)
            courses = cursor.fetchall()
            
            # Get stats for each course
            for course in courses:
                course['stats'] = get_course_stats(course['course_id'])
            
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            flash(f'Error retrieving courses: {err}', 'danger')
    
    return render_template('super_admin/course_management.html', courses=courses)

@super_admin_bp.route('/create_course', methods=['POST'])
@login_required
def create_course():
    data = request.get_json()
    
    # Extract only the required fields
    course_name = data.get('course_name')
    description = data.get('description', '')
    
    # Basic validation for required fields
    errors = {}
    if not course_name:
        errors['course_name'] = 'Course name is required'
    
    if errors:
        return jsonify({'success': False, 'message': 'Validation failed', 'errors': errors})
    
    # Create course
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # MODIFIED INSERT STATEMENT: Only include course_name, description, and created_by
            cursor.execute(
                "INSERT INTO courses (course_name, description, created_by) VALUES (%s, %s, %s)",
                (course_name, description, current_user.user_id)
            )
            course_id = cursor.lastrowid
            conn.commit()
            
            # Log activity
            log_activity(current_user.user_id, 'create', 'courses', course_id, f"Created course: {course_name}")
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Course created successfully', 'course_id': course_id})
        except mysql.connector.Error as err:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error creating course: {err}'})
    
    return jsonify({'success': False, 'message': 'Database connection error'})

@super_admin_bp.route('/update_course/<int:course_id>', methods=['POST'])
@login_required
def update_course(course_id):
    data = request.get_json()
    
    course_name = data.get('course_name')
    description = data.get('description', '')
    is_active = data.get('is_active', False)
    
    # Basic validation
    errors = {}
    if not course_name:
        errors['course_name'] = 'Course name is required'
    
    if errors:
        return jsonify({'success': False, 'message': 'Validation failed', 'errors': errors})
    
    # Update course
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # MODIFIED UPDATE STATEMENT: Only update course_name, description, and is_active
            cursor.execute(
                "UPDATE courses SET course_name = %s, description = %s, is_active = %s WHERE course_id = %s",
                (course_name, description, is_active, course_id)
            )
            conn.commit()
            
            # Log activity
            log_activity(current_user.user_id, 'update', 'courses', course_id, f"Updated course: {course_name}")
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Course updated successfully'})
        except mysql.connector.Error as err:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error updating course: {err}'})
    
    return jsonify({'success': False, 'message': 'Database connection error'})




# _____________________________________________________________________________-



@super_admin_bp.route('/delete_course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # Check if course has students enrolled - USING CORRECT TABLE NAME
            cursor.execute("SELECT COUNT(*) FROM students WHERE course_id = %s", (course_id,))
            student_count = cursor.fetchone()[0]
            
            if student_count > 0:
                return jsonify({'success': False, 'message': 'Cannot delete course with enrolled students'})
            
            # Get course name for logging
            cursor.execute("SELECT course_name FROM courses WHERE course_id = %s", (course_id,))
            course_name = cursor.fetchone()[0]
            
            # First delete related records in course_admins and course_trainers
            cursor.execute("DELETE FROM course_admins WHERE course_id = %s", (course_id,))
            cursor.execute("DELETE FROM course_trainers WHERE course_id = %s", (course_id,))
            
            # Now delete the course
            cursor.execute("DELETE FROM courses WHERE course_id = %s", (course_id,))
            conn.commit()
            
            # Log activity
            log_activity(current_user.user_id, 'delete', 'courses', course_id, f"Deleted course: {course_name}")
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Course deleted successfully'})
        except mysql.connector.Error as err:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error deleting course: {err}'})
    
    return jsonify({'success': False, 'message': 'Database connection error'})


# ______________________________________________________________
@super_admin_bp.route('/create_admin', methods=['GET', 'POST'])
@login_required
def create_admin():
    # Get courses for dropdown (for GET request)
    conn = current_app.get_db_connection()
    courses = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT course_id, course_name FROM courses WHERE is_active = TRUE")
            courses = cursor.fetchall()
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            flash(f'Error retrieving courses: {err}', 'danger')
    
    # If it's a GET request, render the form
    if request.method == 'GET':
        return render_template('super_admin/create_admin.html', courses=courses)
    
    # If it's a POST request, process the form
    content_type = request.headers.get('Content-Type', '')
    is_json = 'application/json' in content_type
    is_form_data = 'multipart/form-data' in content_type
    
    if is_json:
        data = request.get_json()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        phone = data.get('phone')
        course_ids = data.get('course_ids', [])
        profile_picture = None  # File uploads not supported in JSON requests
    elif is_form_data:
        # Handle form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        gender = request.form.get('gender') 
        course_ids = request.form.getlist('course_ids')
        profile_picture = None
        
        # Handle file upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and allowed_file(file.filename):
                # Check file size
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                file.seek(0)
                
                if file_length > current_app.config['MAX_CONTENT_LENGTH']:
                    return jsonify({
                        'success': False, 
                        'errors': {'profile_picture': 'File size exceeds the maximum allowed (2MB)'}
                    })
                
                filename = secure_filename(file.filename)
                # Generate unique filename
                ext = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{email.split('@')[0]}_{int(time.time())}.{ext}"
                
                # --- CORRECTED CODE ---
                # Define the correct folder for profile pictures
                profile_pic_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures')
                # Construct the full path to save the file
                file_path = os.path.join(profile_pic_folder, unique_filename)
                # --- END CORRECTION ---

                file.save(file_path)
                profile_picture = unique_filename
    else:
        # Unknown content type
        return jsonify({'success': False, 'message': 'Unsupported content type'})
    
    # Validate input
    errors = {}
    
    if not first_name or not first_name.strip():
        errors['first_name'] = 'First name is required'
    elif len(first_name.strip()) < 2:
        errors['first_name'] = 'First name must be at least 2 characters'
    
    if not last_name or not last_name.strip():
        errors['last_name'] = 'Last name is required'
    elif len(last_name.strip()) < 2:
        errors['last_name'] = 'Last name must be at least 2 characters'
    
    if not email or not email.strip():
        errors['email'] = 'Email is required'
    elif not validate_email(email):
        errors['email'] = 'Please enter a valid email address'
    
    if not phone or not phone.strip():
        errors['phone'] = 'Phone number is required'
    elif not validate_phone(phone):
        errors['phone'] = 'Please enter a valid phone number (10-15 digits)'
    
    if not gender: errors['gender'] = 'Gender is required.'

    if errors:
        return jsonify({'success': False, 'errors': errors})
    
    full_name = f"{first_name.strip()} {last_name.strip()}"
    email = email.strip().lower()
    phone = phone.strip()
    
    # Check if email already exists
    existing_user = User.get_by_email(email)
    if existing_user:
        return jsonify({'success': False, 'errors': {'email': 'Email already exists in the system'}})
    
    # Generate password using last name and phone
    raw_password = generate_password(last_name, phone)
    hashed_password = hash_password(raw_password)
    
    # Create user
    user_id = User.create_user(email, hashed_password, full_name, phone, 'admin', 
                              current_user.user_id, first_name.strip(), last_name.strip(), None, profile_picture,gender)
    
    if user_id:
        # Assign courses to admin
        conn = current_app.get_db_connection()
        if conn and course_ids:
            try:
                cursor = conn.cursor()
                for course_id in course_ids:
                    cursor.execute(
                        "INSERT INTO course_admins (course_id, admin_id) VALUES (%s, %s)",
                        (course_id, user_id)
                    )
                conn.commit()
                cursor.close()
                conn.close()
            except mysql.connector.Error as err:
                conn.rollback()
                cursor.close()
                conn.close()
                return jsonify({
                    'success': True, 
                    'message': 'Admin created but failed to assign some courses',
                    'warning': True
                })
        
        # Send credentials email
        email_sent = send_credentials_email(email, full_name, email, raw_password)
        
        # Log activity
        log_activity(current_user.user_id, 'create', 'users', user_id, f"Created admin: {full_name}")
        
        return jsonify({
            'success': True, 
            'message': 'Admin created successfully' + ('. Credentials sent via email.' if email_sent else ' but email sending failed. Please notify them manually.'),
            'redirect': url_for('super_admin.dashboard')
        })
    else:
        return jsonify({'success': False, 'message': 'Failed to create admin. Please try again.'})


@super_admin_bp.route('/create_trainer', methods=['GET', 'POST'])
@login_required
def create_trainer():
    # Get courses for dropdown (for GET request)
    conn = current_app.get_db_connection()
    courses = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT course_id, course_name FROM courses WHERE is_active = TRUE")
            courses = cursor.fetchall()
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            flash(f'Error retrieving courses: {err}', 'danger')
    
    # If it's a GET request, render the form
    if request.method == 'GET':
        return render_template('super_admin/create_trainer.html', courses=courses)
    
    # If it's a POST request, process the form
    content_type = request.headers.get('Content-Type', '')
    is_json = 'application/json' in content_type
    is_form_data = 'multipart/form-data' in content_type
    
    if is_json:
        data = request.get_json()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        phone = data.get('phone')
        qualifications = data.get('qualifications', '')
        course_ids = data.get('course_ids', [])
        gender = data.get('gender')
        profile_picture = None  # File uploads not supported in JSON requests
    elif is_form_data:
        # Handle form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        qualifications = request.form.get('qualifications', '')
        course_ids = request.form.getlist('course_ids')
        gender = request.form.get('gender')
        profile_picture = None
        
        # Handle file upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and allowed_file(file.filename):
                # Check file size
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                file.seek(0)
                
                # Use 2MB limit directly instead of relying on config
                MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
                if file_length > MAX_FILE_SIZE:
                    return jsonify({
                        'success': False, 
                        'errors': {'profile_picture': 'File size exceeds the maximum allowed (2MB)'}
                    })
                
                filename = secure_filename(file.filename)
                # Generate unique filename
                ext = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{email.split('@')[0]}_{int(time.time())}.{ext}"

                # Define the correct folder for profile pictures
                profile_pic_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures')
                # Ensure directory exists
                os.makedirs(profile_pic_folder, exist_ok=True)
                # Construct the full path to save the file
                file_path = os.path.join(profile_pic_folder, unique_filename)
                
                file.save(file_path)
                profile_picture = unique_filename
    else:
        # Unknown content type
        return jsonify({'success': False, 'message': 'Unsupported content type'})
    
    # Validate input
    errors = {}
    
    if not first_name or not first_name.strip():
        errors['first_name'] = 'First name is required'
    elif len(first_name.strip()) < 2:
        errors['first_name'] = 'First name must be at least 2 characters'
    
    if not last_name or not last_name.strip():
        errors['last_name'] = 'Last name is required'
    elif len(last_name.strip()) < 2:
        errors['last_name'] = 'Last name must be at least 2 characters'
    
    if not email or not email.strip():
        errors['email'] = 'Email is required'
    elif not validate_email(email):
        errors['email'] = 'Please enter a valid email address'
    
    if not phone or not phone.strip():
        errors['phone'] = 'Phone number is required'
    elif not validate_phone(phone):
        errors['phone'] = 'Please enter a valid phone number (10-15 digits)'

    if not gender: 
        errors['gender'] = 'Gender is required.'
    
    if errors:
        return jsonify({'success': False, 'errors': errors})
    
    full_name = f"{first_name.strip()} {last_name.strip()}"
    email = email.strip().lower()
    phone = phone.strip()
    qualifications = qualifications.strip()
    
    # Check if email already exists
    existing_user = User.get_by_email(email)
    if existing_user:
        return jsonify({'success': False, 'errors': {'email': 'Email already exists in the system'}})
    
    # Generate password using last name and phone
    raw_password = generate_password(last_name, phone)
    hashed_password = hash_password(raw_password)
    
    # Create user - USE POSITIONAL ARGUMENTS LIKE YOUR CREATE_ADMIN ROUTE
    user_id = User.create_user(
        email, 
        hashed_password, 
        full_name, 
        phone, 
        'trainer', 
        current_user.user_id, 
        first_name.strip(), 
        last_name.strip(), 
        qualifications, 
        profile_picture,
        gender
    )
    
    if user_id:
        # Assign courses to trainer
        conn = current_app.get_db_connection()
        if conn and course_ids:
            try:
                cursor = conn.cursor()
                for course_id in course_ids:
                    cursor.execute(
                        "INSERT INTO course_trainers (course_id, trainer_id) VALUES (%s, %s)",
                        (course_id, user_id)
                    )
                conn.commit()
                cursor.close()
                conn.close()
            except mysql.connector.Error as err:
                # Don't rollback the entire operation if course assignment fails
                if conn.is_connected():
                    cursor.close()
                    conn.close()
                return jsonify({
                    'success': True, 
                    'message': 'Trainer created but failed to assign some courses',
                    'warning': True
                })
        
        # Send credentials email
        email_sent = send_credentials_email(email, full_name, email, raw_password)
        
        # Log activity
        log_activity(current_user.user_id, 'create', 'users', user_id, f"Created trainer: {full_name}")
        
        return jsonify({
            'success': True, 
            'message': 'Trainer created successfully' + ('. Credentials sent via email.' if email_sent else ' but email sending failed. Please notify them manually.'),
            'redirect': url_for('super_admin.dashboard')
        })
    else:
        return jsonify({'success': False, 'message': 'Failed to create trainer. Please try again.'})

# ___________________________________

@super_admin_bp.route('/get_users/<role>')
@login_required
def get_users(role):
    if role not in ['admin', 'trainer', 'student']:
        return jsonify({'success': False, 'message': 'Invalid role'})
    
    conn = current_app.get_db_connection()
    users = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # UPDATED TO INCLUDE profile_picture
            cursor.execute("""
                SELECT u.*, COUNT(ca.course_id) as assigned_courses 
                FROM users u 
                LEFT JOIN course_admins ca ON u.user_id = ca.admin_id AND ca.is_active = TRUE
                WHERE u.role = %s 
                GROUP BY u.user_id
                ORDER BY u.created_at DESC
            """, (role,))
            users = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'users': users})
        except mysql.connector.Error as err:
            return jsonify({'success': False, 'message': f'Error retrieving users: {err}'})
    
    return jsonify({'success': False, 'message': 'Database connection error'})



@super_admin_bp.route('/toggle_user_status/<int:user_id>', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT is_active FROM users WHERE user_id = %s", (user_id,))
            current_status = cursor.fetchone()['is_active']
            
            new_status = not current_status
            cursor.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (new_status, user_id))
            conn.commit()
            
            # Log activity
            action = 'activate' if new_status else 'deactivate'
            log_activity(current_user.user_id, action, 'users', user_id, f"User status changed to {action}")
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': f'User {"activated" if new_status else "deactivated"} successfully'})
        except mysql.connector.Error as err:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error updating user status: {err}'})
    
    return jsonify({'success': False, 'message': 'Database connection error'})

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
            conn.rollback()
            cursor.close()
            conn.close()


# ____________

# In admin_management route
@super_admin_bp.route('/admins')
@login_required
def admin_management():
    conn = current_app.get_db_connection()
    admins = []
    courses = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Fixed query to properly get assigned courses
            cursor.execute("""
                SELECT u.user_id, u.first_name, u.last_name, u.email, u.phone, u.is_active, u.profile_picture,
                    CONCAT(u.first_name, ' ', u.last_name) as full_name,
                    GROUP_CONCAT(DISTINCT c.course_name SEPARATOR ', ') as assigned_courses
                FROM users u 
                LEFT JOIN course_admins ca ON u.user_id = ca.admin_id AND ca.is_active = TRUE
                LEFT JOIN courses c ON ca.course_id = c.course_id 
                WHERE u.role = 'admin'
                GROUP BY u.user_id
                ORDER BY u.created_at DESC
            """)
            admins = cursor.fetchall()
            
            # Get all courses for the assign course modal
            cursor.execute("SELECT course_id, course_name FROM courses WHERE is_active = TRUE")
            courses = cursor.fetchall()
            
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            flash(f'Error retrieving admins: {err}', 'danger')
    
    return render_template('super_admin/admin_management.html', admins=admins, courses=courses)

# In trainer_management route
@super_admin_bp.route('/trainers')
@login_required
def trainer_management():
    conn = current_app.get_db_connection()
    trainers = []
    courses = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Fixed query to properly get assigned courses
            cursor.execute("""
                SELECT u.*, GROUP_CONCAT(DISTINCT c.course_name) as assigned_courses
                FROM users u 
                LEFT JOIN course_trainers ct ON u.user_id = ct.trainer_id AND ct.is_active = TRUE
                LEFT JOIN courses c ON ct.course_id = c.course_id 
                WHERE u.role = 'trainer'
                GROUP BY u.user_id
                ORDER BY u.created_at DESC
            """)
            trainers = cursor.fetchall()
            
            # Get all courses for the assign course modal
            cursor.execute("SELECT course_id, course_name FROM courses WHERE is_active = TRUE")
            courses = cursor.fetchall()
            
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            flash(f'Error retrieving trainers: {err}', 'danger')
    
    return render_template('super_admin/trainer_management.html', trainers=trainers, courses=courses)

# ____


@super_admin_bp.route('/assign_course', methods=['POST'])
@login_required
def assign_course():
    user_id = request.form.get('user_id')
    user_type = request.form.get('user_type')
    course_ids = request.form.getlist('course_ids')  # Get list of course IDs
    
    if not all([user_id, user_type]):
        return jsonify({'success': False, 'message': 'User ID and type are required'})
    
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            # First, remove all existing assignments for this user
            if user_type == 'admin':
                cursor.execute(
                    "DELETE FROM course_admins WHERE admin_id = %s",
                    (user_id,)
                )
            elif user_type == 'trainer':
                cursor.execute(
                    "DELETE FROM course_trainers WHERE trainer_id = %s",
                    (user_id,)
                )
            
            # Add new assignments for selected courses
            for course_id in course_ids:
                if user_type == 'admin':
                    cursor.execute(
                        "INSERT INTO course_admins (course_id, admin_id) VALUES (%s, %s)",
                        (course_id, user_id)
                    )
                elif user_type == 'trainer':
                    cursor.execute(
                        "INSERT INTO course_trainers (course_id, trainer_id) VALUES (%s, %s)",
                        (course_id, user_id)
                    )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Courses assigned successfully'})
        except mysql.connector.Error as err:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error assigning courses: {err}'})
    
    return jsonify({'success': False, 'message': 'Database connection error'})


@super_admin_bp.route('/approvals')
def approvals():
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch pending requests with requester name
    cursor.execute("""
        SELECT ar.*, u.full_name as requester_name
        FROM approval_requests ar
        JOIN users u ON ar.requester_id = u.user_id
        WHERE ar.status = 'PENDING'
        ORDER BY ar.created_at DESC
    """)
    requests = cursor.fetchall()
    
    # Fetch target names (Student Names) manually to avoid complex dynamic joins
    for req in requests:
        if req['target_id']:
            cursor.execute("""
                SELECT u.full_name FROM students s 
                JOIN users u ON s.user_id = u.user_id 
                WHERE s.student_id = %s
            """, (req['target_id'],))
            res = cursor.fetchone()
            req['student_name'] = res['full_name'] if res else "Unknown"

    conn.close()
    return render_template('super_admin/approvals.html', requests=requests)

@super_admin_bp.route('/process_approval/<int:request_id>', methods=['POST'])
def process_approval(request_id):
    data = request.json
    decision = data.get('decision') # 'APPROVED' or 'REJECTED'
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM approval_requests WHERE request_id = %s", (request_id,))
        req = cursor.fetchone()
        
        if decision == 'APPROVED':
            # --- 1. HANDLE DROPOUT ---
            if req['action_type'] == 'DROPOUT':
                # Soft Delete Logic:
                # 1. Update Student Status to DROPOUT
                cursor.execute("UPDATE students SET enrollment_status = 'DROPOUT' WHERE student_id = %s", (req['target_id'],))
                # 2. Deactivate User Login (So they can't login, but data remains)
                cursor.execute("""
                    UPDATE users SET is_active = FALSE 
                    WHERE user_id = (SELECT user_id FROM students WHERE student_id = %s)
                """, (req['target_id'],))
                # 3. Mark inactive in batch
                cursor.execute("UPDATE batch_students SET is_active = FALSE WHERE student_id = %s", (req['target_id'],))

            # --- 2. HANDLE LATE ENROLLMENT ---
            elif req['action_type'] == 'LATE_ENROLLMENT':
                payload = json.loads(req['new_data_payload'])
                batch_id = payload['batch_id']
                course_id = payload['course_id']
                
                # Generate ID
                new_id = f"MIT-{datetime.now().year}-{req['target_id']}"
                
                cursor.execute("""
                    UPDATE students SET batch_id=%s, course_id=%s, enrollment_status='ENROLLED', enrollment_id=%s 
                    WHERE student_id=%s
                """, (batch_id, course_id, new_id, req['target_id']))
                
                cursor.execute("INSERT INTO batch_students (batch_id, student_id, is_active) VALUES (%s, %s, TRUE)", (batch_id, req['target_id']))

        # Update Request Status
        cursor.execute("UPDATE approval_requests SET status=%s, approver_id=%s WHERE request_id=%s", 
                       (decision, current_user.user_id, request_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': f'Request {decision}'})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()






@super_admin_bp.route('/create_trainer', methods=['GET'])
@login_required
def create_trainer_form():
    # Get courses for dropdown
    conn = current_app.get_db_connection()
    courses = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT course_id, course_name FROM courses WHERE is_active = TRUE")
            courses = cursor.fetchall()
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            flash(f'Error retrieving courses: {err}', 'danger')
    
    return render_template('super_admin/create_trainer.html', courses=courses)




@super_admin_bp.route('/edit_user', methods=['POST'])
@login_required
def edit_user():
    user_id = request.form.get('user_id')
    user_type = request.form.get('user_type')
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    qualifications = request.form.get('qualifications', None)

    if not all([user_id, user_type, full_name, email, phone]):
        return jsonify({'success': False, 'message': 'All fields are required'})

    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            first_name, last_name = full_name.split(' ', 1) if ' ' in full_name else (full_name, '')
            if user_type == 'admin':
                cursor.execute(
                    "UPDATE users SET first_name=%s, last_name=%s, full_name=%s, email=%s, phone=%s WHERE user_id=%s AND role='admin'",
                    (first_name, last_name, full_name, email, phone, user_id)
                )
            elif user_type == 'trainer':
                cursor.execute(
                    "UPDATE users SET first_name=%s, last_name=%s, full_name=%s, email=%s, phone=%s, qualifications=%s WHERE user_id=%s AND role='trainer'",
                    (first_name, last_name, full_name, email, phone, qualifications, user_id)
                )
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': 'User updated successfully'})
        except mysql.connector.Error as err:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error updating user: {err}'})
    return jsonify({'success': False, 'message': 'Database connection error'})




@super_admin_bp.route('/delete_user', methods=['POST'])
@login_required
def delete_user():
    user_id = request.form.get('user_id')
    user_type = request.form.get('user_type')
    if not all([user_id, user_type]):
        return jsonify({'success': False, 'message': 'User ID and type required'})

    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'})
    try:
        cursor = conn.cursor()
        assigned_count = 0

        if user_type == 'admin':
            cursor.execute("SELECT COUNT(*) FROM course_admins WHERE admin_id=%s", (user_id,))
            assigned_count = cursor.fetchone()[0]
        elif user_type == 'trainer':
            cursor.execute("SELECT COUNT(*) FROM course_trainers WHERE trainer_id=%s", (user_id,))
            assigned_count = cursor.fetchone()[0]
        else:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid user type.'})

        if assigned_count > 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Cannot delete. User has assigned courses.'})

        # Double-check user exists before deleting
        cursor.execute("SELECT user_id FROM users WHERE user_id=%s AND role=%s", (user_id, user_type))
        user_exists = cursor.fetchone()
        if not user_exists:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'User not found.'})

        cursor.execute("DELETE FROM users WHERE user_id=%s AND role=%s", (user_id, user_type))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as err:
        try:
            conn.rollback()
        except Exception:
            pass
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'success': False, 'message': f'Error deleting user: {str(err)}'})
    

    