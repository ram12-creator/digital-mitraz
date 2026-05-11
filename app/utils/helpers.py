
# _____________________________________________________


import re                      # For regular expressions (used in validation).
import bcrypt                  # For secure password hashing.
import random                  # For generating random choices (used in password reset tokens).
import string                  # Provides constants for string characters.
from datetime import datetime, timedelta # For date and time operations.
from flask import current_app  # To access Flask application context (like DB config).
import mysql.connector         # For interacting with MySQL database.
from flask import request      # To access request object (e.g., for IP address logging).

# --- Password Generation and Verification ---

def generate_password(last_name, phone_number):
    """
    Generates a raw password based on the user's last name and phone number.
    This is typically for initial account creation or temporary passwords.
    """
    # Extracts only the digits from the phone number string using regex.
    phone_digits = re.sub(r'\D', '', phone_number)
    # Takes the last 5 digits, padding with zeros if fewer than 5.
    last_five = phone_digits[-5:] if len(phone_digits) >= 5 else phone_digits.zfill(5)
    
    # Combines the last name (you might want to add .lower() or .strip() for consistency)
    # with the extracted phone digits to form a raw password.
    raw_password = f"{last_name}{last_five}"
    return raw_password

def hash_password(password):
    """
    Hashes a given password using bcrypt for secure storage.
    """
    # Encodes password to bytes, generates a salt, hashes, and decodes back to string.
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """
    Verifies if a plain text password matches a stored bcrypt hash.
    """
    # Encodes both password and hash to bytes for comparison with bcrypt.
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_reset_token():
    """
    Generates a random, URL-safe token for password reset links.
    """
    # Creates a 32-character token using alphanumeric characters.
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

# --- Statistics Helper Functions ---

def get_course_stats(course_id):
    """
    Fetches high-level statistics for a specific course.
    """
    conn = current_app.get_db_connection()
    stats = {
        'total_students': 0,
        'active_students': 0,
        'avg_attendance': 0
    }
    
    if not conn:
        return stats
        
    try:
        cursor = conn.cursor(dictionary=True)
        # Get total and active students for the course
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN s.is_active = TRUE THEN 1 ELSE 0 END) as active
            FROM students s 
            WHERE s.course_id = %s
        """, (course_id,))
        student_data = cursor.fetchone()
        if student_data:
            stats['total_students'] = student_data.get('total', 0)
            stats['active_students'] = student_data.get('active', 0)
        
        # Get average attendance for the course
        cursor.execute("""
            SELECT AVG(is_present) * 100 as avg_att
            FROM attendance 
            WHERE course_id = %s
        """, (course_id,))
        attendance_data = cursor.fetchone()
        if attendance_data and attendance_data['avg_att'] is not None:
            stats['avg_attendance'] = round(attendance_data['avg_att'], 1)
        
    except mysql.connector.Error as err:
        print(f"Error getting course stats: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    
    return stats

def get_user_stats(user_id, role):
    conn = current_app.get_db_connection()
    stats = {
        'total_courses': 0, 'total_students': 0, 'pending_leaves': 0, 'active_batches': 0,
        'total_trainers': 0, 'total_admins': 0, 'attendance_percentage': 0,
        'max_leaves': 0, 'remaining_leaves': 0, 'submitted_assignments': 0, 'avg_grade': 0
    }
    
    if not conn: return stats

    try:
        cursor = conn.cursor(dictionary=True)
        
        if role == 'super_admin':
            cursor.execute("SELECT COUNT(*) as total FROM courses")
            stats['total_courses'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM students")
            stats['total_students'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='admin'")
            stats['total_admins'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='trainer'")
            stats['total_trainers'] = cursor.fetchone()['total']

        elif role == 'admin':
            # Count Courses assigned to Admin
            cursor.execute("SELECT COUNT(*) as count FROM course_admins WHERE admin_id = %s", (user_id,))
            stats['total_courses'] = cursor.fetchone()['count']

            # Count Students in Batches managed by Admin's Courses
            cursor.execute("""
                SELECT COUNT(DISTINCT s.student_id) as count 
                FROM students s
                JOIN batches b ON s.batch_id = b.batch_id
                JOIN course_admins ca ON b.course_id = ca.course_id
                WHERE ca.admin_id = %s
            """, (user_id,))
            stats['total_students'] = cursor.fetchone()['count']

            # Count Active Batches (Using 'is_active')
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM batches b
                JOIN course_admins ca ON b.course_id = ca.course_id
                WHERE ca.admin_id = %s AND b.is_active = TRUE
            """, (user_id,))
            stats['active_batches'] = cursor.fetchone()['count']

            # Pending Leaves
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM leave_applications la
                JOIN students s ON la.student_id = s.student_id
                JOIN batches b ON s.batch_id = b.batch_id
                JOIN course_admins ca ON b.course_id = ca.course_id
                WHERE ca.admin_id = %s AND la.status = 'pending'
            """, (user_id,))
            stats['pending_leaves'] = cursor.fetchone()['count']

        elif role == 'trainer':
            cursor.execute("""
                SELECT COUNT(*) as count FROM batches b 
                JOIN course_trainers ct ON b.course_id = ct.course_id 
                WHERE ct.trainer_id = %s AND b.is_active = TRUE
            """, (user_id,))
            stats['active_batches'] = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(DISTINCT s.student_id) as count
                FROM students s
                JOIN batches b ON s.batch_id = b.batch_id
                JOIN course_trainers ct ON b.course_id = ct.course_id
                WHERE ct.trainer_id = %s
            """, (user_id,))
            stats['total_students'] = cursor.fetchone()['count']

        elif role == 'student':
            # Student Stats
            cursor.execute("""
                SELECT 
                    COALESCE(AVG(CASE WHEN status IN ('PRESENT', 'HALF_DAY_MORNING', 'HALF_DAY_AFTERNOON') THEN 1 ELSE 0 END) * 100, 0) as attendance_percentage
                FROM attendance 
                WHERE student_id = (SELECT student_id FROM students WHERE user_id = %s)
            """, (user_id,))
            att = cursor.fetchone()
            stats['attendance_percentage'] = round(att['attendance_percentage'], 1) if att else 0

    except mysql.connector.Error as err:
        print(f"Stats Error: {err}")
    finally:
        if conn.is_connected(): cursor.close(); conn.close()
    
    return stats