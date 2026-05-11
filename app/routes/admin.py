
# ___________________________________________
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models import User
from app.utils.helpers import generate_password, hash_password, get_user_stats
from app.utils.email_service import send_credentials_email,send_leave_status_email
from app.utils.validators import validate_email, validate_phone, validate_date_range
import mysql.connector
from datetime import datetime,timedelta
import csv
import io
from collections import defaultdict
import os
from werkzeug.utils import secure_filename
from flask import render_template, make_response
from xhtml2pdf import pisa
from io import BytesIO
from flask import render_template, request, jsonify, url_for, make_response, current_app
from werkzeug.utils import secure_filename
from xhtml2pdf import pisa
from io import BytesIO
import os
import json
import csv
from io import StringIO


admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
def before_request():
    """Protects all admin routes and ensures the user is an admin."""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('auth.login'))

def log_activity(user_id, action, table_affected, record_id, description):
    """Helper function to log admin activities."""
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO activity_logs (user_id, action, table_affected, record_id, description, ip_address) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, action, table_affected, record_id, description, request.remote_addr)
            )
            conn.commit()
        except mysql.connector.Error as err:
            print(f"Error logging activity: {err}")
            conn.rollback()
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()





@admin_bp.route('/dashboard')
def dashboard():
    stats = get_user_stats(current_user.user_id, 'admin')
    conn = current_app.get_db_connection()
    chart_data = {}
    students_to_watch = []
    pending_leaves_list = []

    if not conn: return render_template('admin/dashboard.html', stats=stats)

    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Course Popularity
        cursor.execute("""
            SELECT c.course_name, COUNT(s.student_id) as student_count
            FROM courses c
            JOIN batches b ON c.course_id = b.course_id
            JOIN students s ON b.batch_id = s.batch_id
            JOIN course_admins ca ON c.course_id = ca.course_id
            WHERE ca.admin_id = %s
            GROUP BY c.course_id, c.course_name
            ORDER BY student_count DESC LIMIT 7
        """, (current_user.user_id,))
        course_popularity = cursor.fetchall()
        chart_data['course_popularity'] = {
            'labels': [row['course_name'] for row in course_popularity],
            'data': [row['student_count'] for row in course_popularity]
        }

        # 2. Leave Breakdown
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM leave_applications la
            JOIN students s ON la.student_id = s.student_id
            LEFT JOIN batches b ON s.batch_id = b.batch_id
            JOIN course_admins ca ON b.course_id = ca.course_id
            WHERE ca.admin_id = %s GROUP BY status
        """, (current_user.user_id,))
        leave_breakdown = cursor.fetchall()
        chart_data['leave_breakdown'] = {
            'labels': [row['status'].title() for row in leave_breakdown],
            'data': [row['count'] for row in leave_breakdown]
        }

        # 3. Attendance Trend (FIXED: Uses 'status' enum)
        cursor.execute("""
            SELECT 
                DATE_FORMAT(a.attendance_date, '%b %Y') as month_name,
                AVG(CASE WHEN a.status IN ('PRESENT', 'HALF_DAY_MORNING', 'HALF_DAY_AFTERNOON') THEN 1 ELSE 0 END) * 100 as avg_attendance
            FROM attendance a
            JOIN batches b ON a.batch_id = b.batch_id
            JOIN course_admins ca ON b.course_id = ca.course_id
            WHERE ca.admin_id = %s AND a.attendance_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY YEAR(a.attendance_date), MONTH(a.attendance_date), month_name
            ORDER BY YEAR(a.attendance_date), MONTH(a.attendance_date)
        """, (current_user.user_id,))
        attendance_trend = cursor.fetchall()
        chart_data['attendance_trend'] = {
            'labels': [row['month_name'] for row in attendance_trend],
            'data': [round(row['avg_attendance'], 1) for row in attendance_trend]
        }

        # 4. Students to Watch (FIXED: Uses 'status' enum)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        cursor.execute("""
            SELECT u.full_name, b.batch_name, 
                   AVG(CASE WHEN a.status IN ('PRESENT', 'HALF_DAY_MORNING', 'HALF_DAY_AFTERNOON') THEN 1 ELSE 0 END) * 100 as attendance_pct
            FROM attendance a 
            JOIN students s ON a.student_id = s.student_id
            JOIN users u ON s.user_id = u.user_id 
            JOIN batches b ON s.batch_id = b.batch_id
            JOIN course_admins ca ON b.course_id = ca.course_id
            WHERE ca.admin_id = %s AND a.attendance_date >= %s
            GROUP BY u.user_id, u.full_name, b.batch_name
            HAVING attendance_pct < 75 ORDER BY attendance_pct ASC LIMIT 5
        """, (current_user.user_id, thirty_days_ago))
        students_to_watch = cursor.fetchall()
        
        # 5. Pending Leaves
        cursor.execute("""
            SELECT u.full_name, la.start_date, la.end_date, la.leave_id
            FROM leave_applications la JOIN students s ON la.student_id = s.student_id
            JOIN users u ON s.user_id = u.user_id 
            LEFT JOIN batches b ON s.batch_id = b.batch_id
            JOIN course_admins ca ON b.course_id = ca.course_id
            WHERE ca.admin_id = %s AND la.status = 'pending'
            ORDER BY la.applied_at ASC LIMIT 5
        """, (current_user.user_id,))
        pending_leaves_list = cursor.fetchall()

    except Exception as err:
        print(f"Dashboard Error: {err}")
    finally:
        conn.close()

    return render_template('admin/dashboard.html', stats=stats, chart_data=chart_data,
                           students_to_watch=students_to_watch, pending_leaves_list=pending_leaves_list)

@admin_bp.route('/api/dashboard_stats', methods=['POST'])
@login_required
def get_dashboard_stats():
    data = request.get_json()
    filter_type = data.get('filter_type', 'month') # day, month, year
    batch_id = data.get('batch_id', 'all')
    
    conn = current_app.get_db_connection()
    response_data = {}
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # --- 1. DYNAMIC ATTENDANCE TREND ---
            # FIX: We construct the date string manually in the GROUP BY logic to avoid ambiguity.
            
            if filter_type == 'day':
                # For DAY: Group by the full date.
                sql_select = "DATE_FORMAT(a.attendance_date, '%Y-%m-%d') as label"
                sql_group = "a.attendance_date" 
                sql_order = "a.attendance_date ASC"
                limit_clause = "LIMIT 30"
                
            elif filter_type == 'month':
                # For MONTH: Group by Year and Month. 
                # We select the formatted string directly based on Year/Month.
                sql_select = "DATE_FORMAT(a.attendance_date, '%b %Y') as label"
                sql_group = "YEAR(a.attendance_date), MONTH(a.attendance_date), DATE_FORMAT(a.attendance_date, '%b %Y')"
                sql_order = "YEAR(a.attendance_date) ASC, MONTH(a.attendance_date) ASC"
                limit_clause = "LIMIT 12"
                
            elif filter_type == 'year':
                # For YEAR: Group by Year.
                sql_select = "DATE_FORMAT(a.attendance_date, '%Y') as label"
                sql_group = "YEAR(a.attendance_date), DATE_FORMAT(a.attendance_date, '%Y')"
                sql_order = "YEAR(a.attendance_date) ASC"
                limit_clause = "LIMIT 5"

            query = f"""
                SELECT 
                    {sql_select},
                    AVG(a.is_present) * 100 as value
                FROM attendance a
                JOIN course_admins ca ON a.course_id = ca.course_id
                WHERE ca.admin_id = %s
            """
            params = [current_user.user_id]

            if batch_id != 'all':
                query += " AND a.batch_id = %s"
                params.append(batch_id)

            query += f" GROUP BY {sql_group} ORDER BY {sql_order} {limit_clause}"
            
            cursor.execute(query, tuple(params))
            att_results = cursor.fetchall()
            
            response_data['attendance'] = {
                'labels': [row['label'] for row in att_results],
                'data': [round(row['value'], 1) for row in att_results]
            }

            # --- 2. BATCH PERFORMANCE (REAL-TIME GRADE) ---
            perf_query = """
                SELECT b.batch_name, AVG(COALESCE(asub.grade, asub.auto_grade)) as avg_grade
                FROM batches b
                JOIN course_admins ca ON b.course_id = ca.course_id
                LEFT JOIN assignments a ON b.batch_id = a.batch_id
                LEFT JOIN assignment_submissions asub ON a.assignment_id = asub.assignment_id
                WHERE ca.admin_id = %s
            """
            perf_params = [current_user.user_id]

            if batch_id != 'all':
                perf_query += " AND b.batch_id = %s"
                perf_params.append(batch_id)

            perf_query += """
                GROUP BY b.batch_id, b.batch_name
                HAVING avg_grade IS NOT NULL
                ORDER BY avg_grade DESC LIMIT 5
            """
            
            cursor.execute(perf_query, tuple(perf_params))
            batch_results = cursor.fetchall()
            
            response_data['batch_performance'] = {
                'labels': [row['batch_name'] for row in batch_results],
                'data': [round(row['avg_grade'], 1) for row in batch_results]
            }
            
            # --- 3. COURSE POPULARITY ---
            cursor.execute("""
                SELECT c.course_name, COUNT(s.student_id) as count
                FROM courses c
                JOIN course_admins ca ON c.course_id = ca.course_id
                LEFT JOIN students s ON c.course_id = s.course_id
                WHERE ca.admin_id = %s
                GROUP BY c.course_id, c.course_name
                LIMIT 7
            """, (current_user.user_id,))
            pop_results = cursor.fetchall()
            response_data['course_popularity'] = {
                'labels': [row['course_name'] for row in pop_results],
                'data': [row['count'] for row in pop_results]
            }

            # --- 4. LEAVE BREAKDOWN ---
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM leave_applications la
                JOIN students s ON la.student_id = s.student_id
                JOIN course_admins ca ON s.course_id = ca.course_id
                WHERE ca.admin_id = %s
                GROUP BY la.status
            """, (current_user.user_id,))
            leave_results = cursor.fetchall()
            response_data['leave_breakdown'] = {
                'labels': [row['status'].title() for row in leave_results],
                'data': [row['count'] for row in leave_results]
            }

            # --- 5. ASSIGNMENT STATUS ---
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN asub.grade IS NOT NULL OR asub.auto_grade IS NOT NULL THEN 1 ELSE 0 END) as graded,
                    SUM(CASE WHEN asub.submission_id IS NOT NULL AND asub.grade IS NULL AND asub.auto_grade IS NULL THEN 1 ELSE 0 END) as submitted_ungraded
                FROM assignment_submissions asub
                JOIN students s ON asub.student_id = s.student_id
                JOIN course_admins ca ON s.course_id = ca.course_id
                WHERE ca.admin_id = %s
            """, (current_user.user_id,))
            assign_status = cursor.fetchone()
            response_data['assignment_status'] = {
                'labels': ['Graded', 'Pending Review'],
                'data': [int(assign_status['graded'] or 0), int(assign_status['submitted_ungraded'] or 0)]
            }

            return jsonify({'success': True, 'data': response_data})

        except Exception as e:
            print(f"API Error: {e}") # This will print to your terminal now
            return jsonify({'success': False, 'message': str(e)})
        finally:
            cursor.close()
            conn.close()
            
    return jsonify({'success': False, 'message': 'DB Connection Error'})


# --- BATCH MANAGEMENT ROUTES  ---



@admin_bp.route('/batches')
def batch_management():
    conn = current_app.get_db_connection()
    courses = []
    batches_by_course = {}
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.course_id, c.course_name 
                FROM courses c JOIN course_admins ca ON c.course_id = ca.course_id 
                WHERE ca.admin_id = %s AND c.is_active = TRUE
            """, (current_user.user_id,))
            courses = cursor.fetchall()
            
            course_ids = [c['course_id'] for c in courses]
            if course_ids:
                placeholders = ', '.join(['%s'] * len(course_ids))
                cursor.execute(f"""
                    SELECT b.*, c.course_name, COUNT(bs.student_id) as student_count
                    FROM batches b
                    JOIN courses c ON b.course_id = c.course_id
                    LEFT JOIN batch_students bs ON b.batch_id = bs.batch_id AND bs.is_active = TRUE
                    WHERE b.course_id IN ({placeholders})
                    GROUP BY b.batch_id
                    ORDER BY c.course_name, b.start_date DESC
                """, tuple(course_ids))
                batches = cursor.fetchall()
                for course in courses:
                    batches_by_course[course['course_id']] = {
                        'course_name': course['course_name'],
                        'batches': [b for b in batches if b['course_id'] == course['course_id']]
                    }
        except mysql.connector.Error as err:
            flash(f'Error retrieving batches: {err}', 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('admin/batch_management.html', courses=courses, batches_by_course=batches_by_course)



@admin_bp.route('/create_batch', methods=['POST'])
def create_batch():
    data = request.get_json()
    batch_name = data.get('batch_name')
    course_id = data.get('course_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    max_students = data.get('max_students')
    
    # --- Capture all new leave limits from the form ---
    personal_leave_limit = data.get('personal_leave_limit')
    medical_leave_limit = data.get('medical_leave_limit')
    academic_leave_limit = data.get('academic_leave_limit')
    special_leave_limit = data.get('special_leave_limit')
    
    
    errors = {}
    if not batch_name or len(batch_name) < 3: errors['batch_name'] = 'Name must be at least 3 characters.'
    if not course_id: errors['course_id'] = 'Please select a course.'
    if not start_date: errors['start_date'] = 'Start date is required.'
    if not end_date: errors['end_date'] = 'End date is required.'
    if start_date and end_date and end_date < start_date: errors['end_date'] = 'End date cannot be before start date.'
    if not max_students or not max_students.isdigit() or int(max_students) < 1: errors['max_students'] = 'Max students must be a positive number.'

    if errors:
        return jsonify({'success': False, 'errors': errors})

    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor()
        # --- MODIFIED INSERT STATEMENT with all leave limits ---
        cursor.execute(
            """INSERT INTO batches (batch_name, course_id, start_date, end_date, max_students, 
                                 personal_leave_limit, medical_leave_limit, academic_leave_limit, special_leave_limit, created_by) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (batch_name, course_id, start_date, end_date, int(max_students), 
             personal_leave_limit, medical_leave_limit, academic_leave_limit, special_leave_limit, current_user.user_id)
        )
        batch_id = cursor.lastrowid
        conn.commit()
        log_activity(current_user.user_id, 'create', 'batches', batch_id, f"Created batch: {batch_name}")
        return jsonify({'success': True, 'message': 'Batch created successfully!'})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# ===============================================================
#Batch Update Logic
# ===============================================================
@admin_bp.route('/update_batch/<int:batch_id>', methods=['POST'])
def update_batch(batch_id):
    data = request.get_json()
    batch_name = data.get('batch_name')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    max_students = data.get('max_students')
    is_active = data.get('is_active')
    
    # --- Capture all new leave limits from the form ---
    personal_leave_limit = data.get('personal_leave_limit')
    medical_leave_limit = data.get('medical_leave_limit')
    academic_leave_limit = data.get('academic_leave_limit')
    special_leave_limit = data.get('special_leave_limit')
    
    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor()
        # --- MODIFIED UPDATE STATEMENT with all leave limits ---
        cursor.execute(
            """UPDATE batches SET batch_name=%s, start_date=%s, end_date=%s, max_students=%s, is_active=%s, 
                                personal_leave_limit=%s, medical_leave_limit=%s, academic_leave_limit=%s, special_leave_limit=%s
               WHERE batch_id=%s""",
            (batch_name, start_date, end_date, max_students, is_active, 
             personal_leave_limit, medical_leave_limit, academic_leave_limit, special_leave_limit, batch_id)
        )
        conn.commit()
        log_activity(current_user.user_id, 'update', 'batches', batch_id, f"Updated batch: {batch_name}")
        return jsonify({'success': True, 'message': 'Batch updated successfully!'})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()









@admin_bp.route('/delete_batch/<int:batch_id>', methods=['POST'])
def delete_batch(batch_id):
    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as count FROM batch_students WHERE batch_id = %s AND is_active = TRUE", (batch_id,))
        if cursor.fetchone()['count'] > 0:
            return jsonify({'success': False, 'message': 'Cannot delete batch with enrolled students.'})
        
        cursor.execute("SELECT batch_name FROM batches WHERE batch_id = %s", (batch_id,))
        batch_name = cursor.fetchone()['batch_name']
        cursor.execute("DELETE FROM batches WHERE batch_id = %s", (batch_id,))
        conn.commit()
        log_activity(current_user.user_id, 'delete', 'batches', batch_id, f"Deleted batch: {batch_name}")
        return jsonify({'success': True, 'message': 'Batch deleted successfully.'})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()







@admin_bp.route('/students', defaults={'batch_id': None})
@admin_bp.route('/students/batch/<int:batch_id>')
def student_management(batch_id):
    conn = current_app.get_db_connection()
    students, courses, batches = [], [], []
    batch_name = None
    
    # --- GET FILTER/CONTEXT PARAMETERS ---
    selected_course_id = request.args.get('course_id', type=int)
    selected_batch_id = request.args.get('batch_id', type=int)

    # If a batch_id is in the URL path (e.g., /students/batch/5), it takes precedence
    if batch_id:
        selected_batch_id = batch_id

    if not conn:
        flash('Database connection error.', 'danger')
        return render_template('admin/student_management.html', students=[], courses=[], batches=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Get all courses this admin manages
        cursor.execute("""
            SELECT c.course_id, c.course_name FROM courses c JOIN course_admins ca ON c.course_id = ca.course_id 
            WHERE ca.admin_id = %s AND c.is_active = TRUE
        """, (current_user.user_id,))
        courses = cursor.fetchall()
        
        # --- FIXED QUERY: Added s.enrollment_id ---
        sql = """
            SELECT s.student_id, u.user_id, u.full_name, u.email, u.phone, u.is_active, u.gender,
                   c.course_name, c.course_id, b.batch_name, b.batch_id, 
                   s.enrollment_id  -- <--- THIS WAS MISSING
            FROM students s 
            JOIN users u ON s.user_id = u.user_id 
            LEFT JOIN courses c ON s.course_id = c.course_id 
            JOIN course_admins ca ON c.course_id = ca.course_id
            LEFT JOIN batches b ON s.batch_id = b.batch_id 
            WHERE ca.admin_id = %s
        """
        params = [current_user.user_id]

        # Apply filters
        if selected_course_id:
            sql += " AND c.course_id = %s"
            params.append(selected_course_id)
            cursor.execute("SELECT batch_id, batch_name FROM batches WHERE course_id = %s AND is_active = TRUE", (selected_course_id,))
            batches = cursor.fetchall()

        if selected_batch_id:
            sql += " AND s.batch_id = %s" # Changed from b.batch_id to s.batch_id for accuracy
            params.append(selected_batch_id)
            cursor.execute("SELECT batch_name, course_id FROM batches WHERE batch_id = %s", (selected_batch_id,))
            batch_result = cursor.fetchone()
            if batch_result:
                batch_name = batch_result['batch_name']
                selected_course_id = batch_result['course_id']
        
        sql += " ORDER BY s.created_at DESC" # Order by newest first
        cursor.execute(sql, tuple(params))
        students = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f'Error retrieving students: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            
    return render_template('admin/student_management.html', 
                           students=students, 
                           courses=courses, 
                           batches=batches,
                           batch_name=batch_name,
                           selected_course=selected_course_id,
                           selected_batch=selected_batch_id)
# ___________________________
# ________________




@admin_bp.route('/create_student', methods=['POST'])
def create_student():
    data = request.get_json()
    full_name, email, phone, course_id, batch_id = data.get('full_name'), data.get('email'), data.get('phone'), data.get('course_id'), data.get('batch_id')
    
    # --- NEW: Get gender from the data ---
    gender = data.get('gender') 

    errors = {}
    if not full_name: errors['full_name'] = 'Full name is required.'
    if not email or not validate_email(email): errors['email'] = 'A valid email is required.'
    if not phone or not validate_phone(phone): errors['phone'] = 'A valid phone number is required.'
    if not course_id: errors['course_id'] = 'Course is required.'
    if not batch_id: errors['batch_id'] = 'Batch is required.'
    # --- NEW: Add validation for gender if it's mandatory ---
    if not gender: errors['gender'] = 'Gender is required.' # Assuming gender is now required
    
    if errors:
        return jsonify({'success': False, 'errors': errors})

    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'success': False, 'errors': {'email': 'This email address is already in use.'}})

        last_name = full_name.split()[-1]
        raw_password = generate_password(last_name, phone)
        hashed_password = hash_password(raw_password)
        
        # --- MODIFIED INSERT STATEMENT: Added gender ---
        cursor.execute("INSERT INTO users (email, password_hash, full_name, phone, role, created_by, gender) VALUES (%s, %s, %s, %s, 'student', %s, %s)",
                       (email, hashed_password, full_name, phone, current_user.user_id, gender)) # Pass gender
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO students (user_id, course_id) VALUES (%s, %s)", (user_id, course_id))
        student_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO batch_students (batch_id, student_id) VALUES (%s, %s)", (batch_id, student_id))
        
        send_credentials_email(email, full_name, email, raw_password)
        conn.commit()
        log_activity(current_user.user_id, 'create', 'students', student_id, f"Created student: {full_name}")
        return jsonify({'success': True, 'message': 'Student created successfully!'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/update_student/<int:student_id>', methods=['POST'])
def update_student(student_id):
    data = request.get_json()
    full_name, email, phone, course_id, batch_id, is_active, user_id = data.get('full_name'), data.get('email'), data.get('phone'), data.get('course_id'), data.get('batch_id'), data.get('is_active'), data.get('user_id')

    errors = {} # Add validation as needed
    if errors: return jsonify({'success': False, 'errors': errors})

    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET full_name=%s, email=%s, phone=%s, is_active=%s WHERE user_id=%s",
                       (full_name, email, phone, is_active, user_id))
        
        cursor.execute("UPDATE students SET course_id=%s WHERE student_id=%s", (course_id, student_id))
        
        # Update batch assignment: deactivate old, insert/update new
        cursor.execute("UPDATE batch_students SET is_active=FALSE WHERE student_id=%s", (student_id,))
        if batch_id:
            cursor.execute("INSERT INTO batch_students (batch_id, student_id, is_active) VALUES (%s, %s, TRUE) ON DUPLICATE KEY UPDATE is_active=TRUE",
                           (batch_id, student_id))
        
        conn.commit()
        log_activity(current_user.user_id, 'update', 'students', student_id, f"Updated student: {full_name}")
        return jsonify({'success': True, 'message': 'Student updated successfully!'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@admin_bp.route('/delete_student/<int:user_id>', methods=['POST'])
def delete_student(user_id):
    # Note: Deleting a user will cascade and delete their student record due to DB constraints
    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT full_name FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
             return jsonify({'success': False, 'message': 'User not found.'})
        
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        log_activity(current_user.user_id, 'delete', 'users', user_id, f"Deleted student: {user['full_name']}")
        return jsonify({'success': True, 'message': 'Student deleted successfully.'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Cannot delete student. They may have dependent records (submissions, etc). Error: {err}'})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- ATTENDANCE & LEAVE MANAGEMENT (Largely unchanged but reviewed for compatibility) ---
@admin_bp.route('/attendance')
def attendance_management():
    conn = current_app.get_db_connection()
    courses, batches, attendance_data = [], [], []
    selected_course = request.args.get('course_id')
    selected_batch = request.args.get('batch_id')
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT c.course_id, c.course_name FROM courses c JOIN course_admins ca ON c.course_id = ca.course_id WHERE ca.admin_id = %s AND c.is_active = TRUE", (current_user.user_id,))
            courses = cursor.fetchall()
            
            if selected_course:
                 cursor.execute("SELECT batch_id, batch_name FROM batches WHERE course_id = %s AND is_active = TRUE", (selected_course,))
                 batches = cursor.fetchall()

            if selected_batch and selected_date:
                # Updated query to fetch 'status' instead of 'is_present' based on your new DB schema
                cursor.execute("""
                    SELECT 
                        s.student_id, u.full_name, u.email, a.status,
                        CASE WHEN a.attendance_id IS NOT NULL THEN TRUE ELSE FALSE END as marked
                    FROM students s
                    JOIN users u ON s.user_id = u.user_id
                    JOIN batch_students bs ON s.student_id = bs.student_id
                    LEFT JOIN attendance a ON s.student_id = a.student_id AND a.attendance_date = %s
                    WHERE bs.batch_id = %s AND bs.is_active = TRUE
                    ORDER BY u.full_name
                """, (selected_date, selected_batch))
                attendance_data = cursor.fetchall()
        except mysql.connector.Error as err:
            flash(f'Error retrieving data: {err}', 'danger')
        finally:
            if conn.is_connected(): cursor.close(); conn.close()
    
    return render_template('admin/attendance.html', 
                           courses=courses, 
                           batches=batches, 
                           attendance_data=attendance_data,
                           selected_course=selected_course, 
                           selected_batch=selected_batch, 
                           selected_date=selected_date,
                           now=datetime.now())

# @admin_bp.route('/mark_attendance', methods=['POST'])
# def mark_attendance():
#     data = request.get_json()
#     batch_id = data.get('batch_id')
#     attendance_date = data.get('attendance_date')
#     present_ids = data.get('present_ids', [])
#     absent_ids = data.get('absent_ids', [])

#     if not all([batch_id, attendance_date]):
#         return jsonify({'success': False, 'message': 'Batch and date are required.'})
    
#     conn = current_app.get_db_connection()
#     try:
#         cursor = conn.cursor(dictionary=True)
#         cursor.execute("SELECT course_id FROM batches WHERE batch_id = %s", (batch_id,))
#         course_id = cursor.fetchone()['course_id']
        
#         # Use INSERT ... ON DUPLICATE KEY UPDATE for efficiency
#         attendance_records = []
#         for student_id in present_ids:
#             attendance_records.append((student_id, course_id, batch_id, attendance_date, True, current_user.user_id))
#         for student_id in absent_ids:
#             attendance_records.append((student_id, course_id, batch_id, attendance_date, False, current_user.user_id))
            
#         if attendance_records:
#             query = """
#                 INSERT INTO attendance (student_id, course_id, batch_id, attendance_date, is_present, marked_by)
#                 VALUES (%s, %s, %s, %s, %s, %s)
#                 ON DUPLICATE KEY UPDATE is_present = VALUES(is_present), marked_by = VALUES(marked_by)
#             """
#             cursor.executemany(query, attendance_records)
#             conn.commit()
#             log_activity(current_user.user_id, 'update', 'attendance', batch_id, f"Marked attendance for batch {batch_id} on {attendance_date}")
#             return jsonify({'success': True, 'message': 'Attendance saved successfully!'})
#         return jsonify({'success': True, 'message': 'No changes to save.'})
#     except mysql.connector.Error as err:
#         conn.rollback()
#         return jsonify({'success': False, 'message': f'Database error: {err}'})
#     finally:
#         if conn.is_connected(): cursor.close(); conn.close()


# @admin_bp.route('/mark_attendance', methods=['POST'])
# def mark_attendance():
#     data = request.get_json()
#     batch_id = data.get('batch_id')
#     attendance_date = data.get('attendance_date')
    
#     # New Data Structure: expected to be {student_id: "PRESENT", student_id: "HALF_DAY_MORNING", ...}
#     attendance_map = data.get('attendance_map', {}) 

#     if not all([batch_id, attendance_date]):
#         return jsonify({'success': False, 'message': 'Batch and date are required.'})
    
#     conn = current_app.get_db_connection()
#     try:
#         cursor = conn.cursor(dictionary=True)
        
#         # 1. Check if the date is a Holiday
#         cursor.execute("SELECT title FROM holidays WHERE holiday_date = %s", (attendance_date,))
#         holiday = cursor.fetchone()
        
#         # 2. Get course ID
#         cursor.execute("SELECT course_id FROM batches WHERE batch_id = %s", (batch_id,))
#         course_id = cursor.fetchone()['course_id']
        
#         attendance_records = []
        
#         for student_id, status in attendance_map.items():
#             final_status = status
#             notes = None
            
#             # If it's a holiday, force status to HOLIDAY regardless of input
#             if holiday:
#                 final_status = 'HOLIDAY'
#                 notes = holiday['title']
                
#             attendance_records.append((
#                 student_id, course_id, batch_id, attendance_date, final_status, current_user.user_id, notes
#             ))
            
#         if attendance_records:
#             # Upsert Query for new Status column
#             query = """
#                 INSERT INTO attendance (student_id, course_id, batch_id, attendance_date, status, marked_by, notes)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s)
#                 ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by), notes = VALUES(notes)
#             """
#             cursor.executemany(query, attendance_records)
#             conn.commit()
            
#             msg = f"Attendance saved for {attendance_date}."
#             if holiday: msg += f" Note: Marked as Holiday ({holiday['title']})."
            
#             return jsonify({'success': True, 'message': msg})
            
#         return jsonify({'success': True, 'message': 'No students to mark.'})
#     except mysql.connector.Error as err:
#         conn.rollback()
#         return jsonify({'success': False, 'message': f'Database error: {err}'})
#     finally:
#         if conn.is_connected(): cursor.close(); conn.close()

@admin_bp.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.get_json()
    batch_id = data.get('batch_id')
    attendance_date = data.get('attendance_date')
    attendance_map = data.get('attendance_map', {}) 

    if not all([batch_id, attendance_date]):
        return jsonify({'success': False, 'message': 'Batch and date are required.'})

    # --- NEW SECURITY CHECK: PREVENT BACKDATING ---
    today_str = datetime.now().strftime('%Y-%m-%d')
    if attendance_date != today_str:
        return jsonify({
            'success': False, 
            'message': f'Action Denied: You can only mark attendance for today ({today_str}).'
        }), 403
    # ---------------------------------------------
    
    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Check if the date is a Holiday
        cursor.execute("SELECT title FROM holidays WHERE holiday_date = %s", (attendance_date,))
        holiday = cursor.fetchone()
        
        # 2. Get course ID
        cursor.execute("SELECT course_id FROM batches WHERE batch_id = %s", (batch_id,))
        batch_row = cursor.fetchone()
        
        if not batch_row:
             return jsonify({'success': False, 'message': 'Invalid Batch.'})
             
        course_id = batch_row['course_id']
        
        attendance_records = []
        
        for student_id, status in attendance_map.items():
            final_status = status
            notes = None
            
            if holiday:
                final_status = 'HOLIDAY'
                notes = holiday['title']
                
            attendance_records.append((
                student_id, course_id, batch_id, attendance_date, final_status, current_user.user_id, notes
            ))
            
        if attendance_records:
            query = """
                INSERT INTO attendance (student_id, course_id, batch_id, attendance_date, status, marked_by, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by), notes = VALUES(notes)
            """
            cursor.executemany(query, attendance_records)
            conn.commit()
            
            msg = f"Attendance saved for {attendance_date}."
            if holiday: msg += f" Note: Marked as Holiday ({holiday['title']})."
            
            return jsonify({'success': True, 'message': msg})
            
        return jsonify({'success': True, 'message': 'No students to mark.'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn.is_connected(): cursor.close(); conn.close()





@admin_bp.route('/export_attendance/<int:batch_id>')
def export_attendance(batch_id):
    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error', 'danger')
        return redirect(url_for('admin.attendance_management'))

    try:
        cursor = conn.cursor(dictionary=True)
        
        # BUG FIX: Added JOIN to the 'courses' table aliased as 'c'
        cursor.execute("""
            SELECT b.batch_name, c.course_name 
            FROM batches b
            JOIN courses c ON b.course_id = c.course_id
            JOIN course_admins ca ON b.course_id = ca.course_id
            WHERE ca.admin_id = %s AND b.batch_id = %s
        """, (current_user.user_id, batch_id))
        batch_details = cursor.fetchone()

        if not batch_details:
            flash('Access denied to this batch.', 'danger')
            return redirect(url_for('admin.attendance_management'))
        
        cursor.execute("SELECT DISTINCT attendance_date FROM attendance WHERE batch_id = %s ORDER BY attendance_date", (batch_id,))
        dates = [row['attendance_date'] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT s.student_id, u.full_name, u.email FROM students s
            JOIN users u ON s.user_id = u.user_id
            JOIN batch_students bs ON s.student_id = bs.student_id
            WHERE bs.batch_id = %s AND bs.is_active = TRUE ORDER BY u.full_name
        """, (batch_id,))
        students = cursor.fetchall()
        
        cursor.execute("SELECT student_id, attendance_date, is_present FROM attendance WHERE batch_id = %s", (batch_id,))
        attendance_records = cursor.fetchall()
        
        attendance_map = {(rec['student_id'], rec['attendance_date']): ('P' if rec['is_present'] else 'A') for rec in attendance_records}

        output = io.StringIO()
        writer = csv.writer(output)
        
        header = ['Student Name', 'Email', 'Total Present', 'Total Absent'] + [d.strftime('%Y-%m-%d') for d in dates]
        writer.writerow(header)

        for student in students:
            total_present = 0
            attendance_statuses = []
            for date in dates:
                status = attendance_map.get((student['student_id'], date), '-')
                if status == 'P':
                    total_present += 1
                attendance_statuses.append(status)
            
            total_absent = len([s for s in attendance_statuses if s == 'A'])
            
            row = [student['full_name'], student['email'], total_present, total_absent]
            row.extend(attendance_statuses)
            writer.writerow(row)

        response = current_app.response_class(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename=attendance_{batch_details["batch_name"]}.csv'}
        )
        log_activity(current_user.user_id, 'export', 'attendance', batch_id, f"Exported attendance for {batch_details['batch_name']}")
        return response

    except mysql.connector.Error as err:
        flash(f'Error exporting attendance: {err}', 'danger')
        return redirect(url_for('admin.attendance_management'))
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
        # ________________


# ===============================================================
# MODIFICATION 3: Update Leave Management View
# ===============================================================
@admin_bp.route('/leave_management')
def leave_management():
    conn = current_app.get_db_connection()
    leave_applications = []
    leave_types = []
    student_data = None # For the application form part
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # --- MODIFIED QUERY to get leave type and batch name ---
            cursor.execute("""   
                SELECT 
                    la.*, 
                    u.full_name as student_name, 
                    b.batch_name, 
                    lt.type_name,
                    (SELECT COUNT(*) FROM leave_applications la2 WHERE la2.student_id = la.student_id AND la2.status = 'approved') as approved_leaves
                FROM leave_applications la
                JOIN students s ON la.student_id = s.student_id
                JOIN users u ON s.user_id = u.user_id
                JOIN course_admins ca ON s.course_id = ca.course_id
                LEFT JOIN leave_types lt ON la.leave_type_id = lt.leave_type_id
                LEFT JOIN batches b ON la.batch_id = b.batch_id
                WHERE ca.admin_id = %s
                ORDER BY la.applied_at DESC
            """, (current_user.user_id,))
            leave_applications = cursor.fetchall()

            # Fetch leave types for the form dropdown
            cursor.execute("SELECT leave_type_id, type_name FROM leave_types ORDER BY type_name")
            leave_types = cursor.fetchall()
            
            # Fetch student's own batch for the form (if an admin is also a student in a weird case, or for future use)
            # This part is more relevant for the student's view but good to have the logic ready
            cursor.execute("""
                SELECT s.student_id, b.batch_id, b.batch_name, s.course_id
                FROM students s
                JOIN batch_students bs ON s.student_id = bs.student_id AND bs.is_active = TRUE
                JOIN batches b ON bs.batch_id = b.batch_id
                WHERE s.user_id = %s
            """, (current_user.user_id,))
            student_data = cursor.fetchone()

        except mysql.connector.Error as err:
            flash(f'Error retrieving leaves: {err}', 'danger')
        finally:
            if conn.is_connected(): cursor.close(); conn.close()
            
    return render_template('admin/leave_management.html', 
                           leave_applications=leave_applications, 
                           leave_types=leave_types, 
                           student_data=student_data, 
                           now=datetime.now())


        
@admin_bp.route('/get_batches/<int:course_id>')
def get_batches(course_id):
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT batch_id, batch_name FROM batches WHERE course_id = %s AND is_active = TRUE ORDER BY batch_name", (course_id,))
            batches = cursor.fetchall()
            return jsonify({'success': True, 'batches': batches})
        except mysql.connector.Error as err:
            return jsonify({'success': False, 'message': str(err)})
        finally:
            if conn.is_connected(): cursor.close(); conn.close()
    return jsonify({'success': False, 'message': 'Database connection error.'})







# ===============================================================
# MODIFICATION 4: Update Leave Status Logic (for email notifications)
# ===============================================================
@admin_bp.route('/update_leave_status/<int:leave_id>', methods=['POST'])
def update_leave_status(leave_id):
    data = request.get_json()
    status = data.get('status')
    comments = data.get('comments', '')

    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor()
        # Updated to use reviewed_by and reviewed_at
        cursor.execute("""
            UPDATE leave_applications 
            SET status=%s, reviewed_by=%s, reviewed_at=NOW(), admin_comments=%s 
            WHERE leave_id=%s
        """, (status, current_user.user_id, comments, leave_id))
        conn.commit()
        
        # (Optional) Send Email Logic Here
        
        return jsonify({'success': True, 'message': f'Leave {status}.'})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        conn.close()

@admin_bp.route('/toggle_student_status/<int:user_id>', methods=['POST'])
@login_required
def toggle_student_status(user_id):
    """Toggles the active status of a student user."""
    data = request.get_json()
    new_status = data.get('is_active')

    if new_status is None:
        return jsonify({'success': False, 'message': 'Missing status information.'}), 400

    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500

    try:
        cursor = conn.cursor()
        # Ensure the user being modified is indeed a student to prevent misuse
        cursor.execute("UPDATE users SET is_active = %s WHERE user_id = %s AND role = 'student'", (new_status, user_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'message': 'Student not found or user is not a student.'}), 404
            
        conn.commit()
        
        # Log this important activity
        action_description = "Activated" if new_status else "Deactivated"
        log_activity(current_user.user_id, 'update_status', 'users', user_id, f"{action_description} student account (ID: {user_id})")
        
        return jsonify({'success': True, 'message': f'Student status has been successfully updated to {"Active" if new_status else "Inactive"}.'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@admin_bp.route('/get_student_details/<int:student_id>')
def get_student_details(student_id):
    conn = current_app.get_db_connection()
    if not conn: return jsonify({'success': False, 'message': 'Database connection error'})

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch Basic Info & Profile Picture (Ensure u.profile_picture is selected)
        cursor.execute("""
            SELECT s.student_id, u.full_name, u.email, u.phone, u.profile_picture, u.is_active,
                   b.batch_name, c.course_name, s.enrollment_status, s.enrollment_id,
                   spd.aadhar_number, spd.city, spd.blood_group
            FROM students s
            JOIN users u ON s.user_id = u.user_id
            LEFT JOIN batches b ON s.batch_id = b.batch_id
            LEFT JOIN courses c ON b.course_id = c.course_id
            LEFT JOIN student_personal_details spd ON s.student_id = spd.student_id
            WHERE s.student_id = %s
        """, (student_id,))
        details = cursor.fetchone()

        if not details: 
            return jsonify({'success': False, 'message': 'Student not found'})

        # 2. Calculate Attendance Stats
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status IN ('PRESENT', 'HALF_DAY_MORNING', 'HALF_DAY_AFTERNOON') THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN status = 'ABSENT' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN status LIKE 'HALF%%' THEN 1 ELSE 0 END) as half_day_count,
                SUM(CASE WHEN status = 'LEAVE' THEN 1 ELSE 0 END) as leave_count,
                COUNT(*) as total_days
            FROM attendance 
            WHERE student_id = %s
        """, (student_id,))
        att_stats = cursor.fetchone()
        
        # Calculate Percentage
        total = att_stats['total_days']
        present = att_stats['present_count']
        att_percentage = round((present / total * 100), 1) if total > 0 else 0
        details['attendance_percentage'] = att_percentage

        # 3. Recent Attendance History
        cursor.execute("SELECT attendance_date, status, notes FROM attendance WHERE student_id = %s ORDER BY attendance_date DESC LIMIT 10", (student_id,))
        att_history = cursor.fetchall()
        for r in att_history: r['attendance_date'] = r['attendance_date'].strftime('%d-%b-%Y')

        # 4. Leave History
        cursor.execute("SELECT start_date, end_date, reason, status, admin_comments FROM leave_applications WHERE student_id = %s ORDER BY start_date DESC", (student_id,))
        leaves = cursor.fetchall()
        for l in leaves: 
            l['start_date'] = l['start_date'].strftime('%d-%b-%Y')
            l['end_date'] = l['end_date'].strftime('%d-%b-%Y')

        return jsonify({
            'success': True, 
            'details': details,
            'att_stats': att_stats,
            'att_history': att_history,
            'leaves': leaves
        })

    except Exception as e:
        print(f"Error fetching student details: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()


@admin_bp.route('/holidays', methods=['GET', 'POST'])
def holiday_management():
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Admin adding a new holiday
        title = request.form.get('title')
        date_str = request.form.get('date')
        year = datetime.strptime(date_str, '%Y-%m-%d').year
        
        try:
            cursor.execute("INSERT INTO holidays (holiday_date, title, year) VALUES (%s, %s, %s)", 
                           (date_str, title, year))
            conn.commit()
            flash('Holiday added successfully!', 'success')
            # Log this action
            log_activity(current_user.user_id, 'create', 'holidays', cursor.lastrowid, f"Added holiday: {title}")
        except mysql.connector.Error as err:
            flash(f'Error adding holiday: {err}', 'danger')

    # Fetch holidays for the list
    cursor.execute("SELECT * FROM holidays ORDER BY holiday_date DESC")
    holidays = cursor.fetchall()
    
    conn.close()
    return render_template('admin/holidays.html', holidays=holidays)

@admin_bp.route('/delete_holiday/<int:holiday_id>', methods=['POST'])
def delete_holiday(holiday_id):
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM holidays WHERE holiday_id = %s", (holiday_id,))
        conn.commit()
        flash('Holiday deleted.', 'success')
    except mysql.connector.Error as err:
        flash(f'Error: {err}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('admin.holiday_management'))



    # ===============================================================
# STUDENT ENROLLMENT WIZARD ROUTES
# ===============================================================

# @admin_bp.route('/add_student_wizard')
# def add_student_wizard():
#     conn = current_app.get_db_connection()
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("SELECT batch_id, batch_name FROM batches WHERE is_active = TRUE")
#     batches = cursor.fetchall()
#     conn.close()
    
#     return render_template('admin/add_student.html', 
#                            batches=batches,
#                            mode='create',
#                            student_id=None,
#                            # CRITICAL FIX: Pass 'student' as None explicitly
#                            student=None, 
#                            basic={},
#                            socio={},
#                            education=[],
#                            family=[],
#                            experience={},
#                            counselling={},
#                            documents=[],
#                            placement={})
@admin_bp.route('/add_student_wizard')
def add_student_wizard():
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT batch_id, batch_name FROM batches WHERE is_active = TRUE")
    batches = cursor.fetchall()
    conn.close()
    
    # Pass 'None' and empty dicts to prevent Jinja errors
    return render_template('admin/add_student.html', 
                           batches=batches, mode='create', student_id=None, student=None,
                           basic={}, socio={}, education=[], family=[], experience={}, 
                           counselling={}, documents=[], placement={})

# # --- API 1: Save Basic Details (Creates User & Student ID) ---
# @admin_bp.route('/api/save_basic_details', methods=['POST'])
# def save_basic_details():
#     data = request.form
#     conn = current_app.get_db_connection()
#     cursor = conn.cursor(dictionary=True)
    
#     try:
#         # 1. Create User Account first
#         email = data.get('email')
#         phone = data.get('phone')
        
#         # Check duplicate
#         cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
#         if cursor.fetchone():
#             return jsonify({'success': False, 'message': 'Email already exists.'})

#         # Auto-generate password
#         raw_password = generate_password(data.get('last_name', 'Student'), phone)
#         hashed_pw = hash_password(raw_password)
        
#         cursor.execute("""
#             INSERT INTO users (email, password_hash, full_name, phone, role, first_name, last_name, gender) 
#             VALUES (%s, %s, %s, %s, 'student', %s, %s, %s)
#         """, (email, hashed_pw, f"{data['first_name']} {data['last_name']}", phone, 
#               data['first_name'], data['last_name'], data['gender']))
#         user_id = cursor.lastrowid
        
#         # 2. Create Student Record
#         cursor.execute("INSERT INTO students (user_id, enrollment_status) VALUES (%s, 'DRAFT')", (user_id,))
#         student_id = cursor.lastrowid
        
#         # 3. Insert Detailed Profile
#         cursor.execute("""
#             INSERT INTO student_personal_details (
#                 student_id, aadhar_number, dob, blood_group, marital_status, 
#                 religion, category, father_name, city, pincode
#             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#         """, (
#             student_id, data.get('aadhar'), data.get('dob'), data.get('blood_group'),
#             data.get('marital'), data.get('religion'), data.get('category'),
#             data.get('father_name'), data.get('city'), data.get('pincode')
#         ))
        
#         # Send credentials (optional here, or at final step)
#         send_credentials_email(email, data['first_name'], email, raw_password)
        
#         conn.commit()
#         return jsonify({'success': True, 'student_id': student_id, 'message': 'Basic details saved. Proceed to next tab.'})
        
#     except mysql.connector.Error as err:
#         conn.rollback()
#         return jsonify({'success': False, 'message': f'Database Error: {err}'})
#     finally:
#         conn.close()

# --- API: Save Basic Details (Handles Insert AND Update) ---
@admin_bp.route('/api/save_basic_details', methods=['POST'])
def save_basic_details():
    data = request.form
    student_id = data.get('student_id')
    
    # --- 1. HANDLE FILE UPLOAD ---
    photo_filename = None
    if 'profile_photo' in request.files:
        file = request.files['profile_photo']
        if file.filename != '':
            # Secure name: phone_filename.jpg (to prevent duplicates/overwrites)
            ext = os.path.splitext(file.filename)[1]
            safe_name = secure_filename(f"{data['phone']}_profile{ext}")
            
            # Ensure directory exists
            upload_path = os.path.join(current_app.root_path, 'static/uploads/profile_pictures')
            os.makedirs(upload_path, exist_ok=True)
            
            file.save(os.path.join(upload_path, safe_name))
            photo_filename = safe_name

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Extract fields
        email = data.get('email')
        phone = data.get('phone')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        gender = data.get('gender')
        
        # --- SCENARIO A: CREATE NEW STUDENT ---
        if not student_id or student_id == 'null' or student_id == 'None' or student_id == '':
            
            # Check duplicate email
            cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Email already exists!'})

            # Generate Password & Hash
            # Logic: Lastname + Last 5 digits of phone
            last_name_clean = last_name.strip().replace(' ', '')
            phone_clean = phone.strip()
            last_5_digits = phone_clean[-5:] if len(phone_clean) >= 5 else phone_clean.zfill(5)
            
            raw_password = f"{last_name_clean}{last_5_digits}"
            hashed_pw = hash_password(raw_password)
            
            # Insert User (With Photo if exists)
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, phone, role, first_name, last_name, gender, profile_picture) 
                VALUES (%s, %s, %s, %s, 'student', %s, %s, %s, %s)
            """, (email, hashed_pw, f"{first_name} {last_name}", phone, first_name, last_name, gender, photo_filename))
            user_id = cursor.lastrowid
            
            # Insert Student
            cursor.execute("INSERT INTO students (user_id, enrollment_status) VALUES (%s, 'DRAFT')", (user_id,))
            student_id = cursor.lastrowid
            
            # Insert Personal Details (NO MIDDLE NAME)
            query = """
                INSERT INTO student_personal_details 
                (student_id, aadhar_number, dob, blood_group, marital_status, religion, category, 
                 salutation, mobilization_channel, refered_by, bpl_status, 
                 current_address, city, pincode, permanent_address, primary_phone, primary_email,
                 spouse_name, children_count) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                student_id, 
                data.get('aadhar'), data.get('dob'), data.get('blood_group'), 
                data.get('marital_status'), data.get('religion'), data.get('category'), 
                data.get('salutation'), data.get('mobilization_channel'), 
                data.get('refered_by'), data.get('bpl_status'), 
                data.get('present_address1'), data.get('present_city'), data.get('present_pincode'), 
                data.get('perm_address1'), phone, email,
                data.get('spouse_name'), data.get('children_count')
            )
            cursor.execute(query, params)
            msg = "Student Created Successfully"

            # Send Email (Silent fail if error)
            try:
                send_credentials_email(email, first_name, email, raw_password)
            except:
                print("Email sending failed")

        # --- SCENARIO B: UPDATE EXISTING STUDENT ---
        else:
            # Update Personal Details
            query = """
                UPDATE student_personal_details SET 
                aadhar_number=%s, dob=%s, blood_group=%s, marital_status=%s, religion=%s, category=%s, 
                salutation=%s, mobilization_channel=%s, refered_by=%s, bpl_status=%s, 
                current_address=%s, city=%s, pincode=%s, permanent_address=%s, primary_phone=%s, primary_email=%s,
                spouse_name=%s, children_count=%s
                WHERE student_id=%s
            """
            params = (
                data.get('aadhar'), data.get('dob'), data.get('blood_group'), 
                data.get('marital_status'), data.get('religion'), data.get('category'), 
                data.get('salutation'), data.get('mobilization_channel'), 
                data.get('refered_by'), data.get('bpl_status'), 
                data.get('present_address1'), data.get('present_city'), data.get('present_pincode'), 
                data.get('perm_address1'), phone, email, 
                data.get('spouse_name'), data.get('children_count'),
                student_id
            )
            cursor.execute(query, params)
            
            # Update User Table (Handle Photo Update)
            if photo_filename:
                # Update WITH new photo
                cursor.execute("""
                    UPDATE users SET first_name=%s, last_name=%s, full_name=%s, phone=%s, email=%s, gender=%s, profile_picture=%s 
                    WHERE user_id = (SELECT user_id FROM students WHERE student_id=%s)
                """, (first_name, last_name, f"{first_name} {last_name}", phone, email, gender, photo_filename, student_id))
            else:
                # Update WITHOUT changing existing photo
                cursor.execute("""
                    UPDATE users SET first_name=%s, last_name=%s, full_name=%s, phone=%s, email=%s, gender=%s 
                    WHERE user_id = (SELECT user_id FROM students WHERE student_id=%s)
                """, (first_name, last_name, f"{first_name} {last_name}", phone, email, gender, student_id))
            
            msg = "Profile Updated Successfully"

        conn.commit()
        return jsonify({'success': True, 'student_id': student_id, 'message': msg})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f"System Error: {str(e)}"})
    finally:
        conn.close()

# --- API 2: Save Family Details ---
@admin_bp.route('/api/save_family_details', methods=['POST'])
def save_family_details():
    data = request.json # Expecting JSON list of family members
    student_id = data.get('student_id')
    members = data.get('members', [])
    
    if not student_id: return jsonify({'success': False, 'message': 'Student ID missing'})
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        # Clear existing to allow updates
        cursor.execute("DELETE FROM student_family WHERE student_id = %s", (student_id,))
        
        for m in members:
            cursor.execute("""
                INSERT INTO student_family (student_id, name, relationship, occupation, income)
                VALUES (%s, %s, %s, %s, %s)
            """, (student_id, m['name'], m['relationship'], m['occupation'], m['income']))
            
        conn.commit()
        return jsonify({'success': True, 'message': 'Family details saved.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# --- API 3: Save Education ---
@admin_bp.route('/api/save_education', methods=['POST'])
def save_education():
    data = request.json
    student_id = data.get('student_id')
    qualifications = data.get('qualifications', [])
    
    if not student_id: return jsonify({'success': False, 'message': 'Student ID missing'})
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM student_education WHERE student_id = %s", (student_id,))
        for q in qualifications:
            cursor.execute("""
                INSERT INTO student_education (student_id, qualification_level, institute_name, passing_year, percentage)
                VALUES (%s, %s, %s, %s, %s)
            """, (student_id, q['level'], q['institute'], q['year'], q['percentage']))
            
        conn.commit()
        return jsonify({'success': True, 'message': 'Education details saved.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# # --- API 4: Finalize Enrollment ---
# @admin_bp.route('/api/finalize_enrollment', methods=['POST'])
# def finalize_enrollment():
#     data = request.json
#     student_id = data.get('student_id')
#     batch_id = data.get('batch_id')
    
#     conn = current_app.get_db_connection()
#     cursor = conn.cursor()
#     try:
#         # Link to batch and set Active
#         cursor.execute("""
#             UPDATE students SET batch_id = %s, enrollment_status = 'ENROLLED' 
#             WHERE student_id = %s
#         """, (batch_id, student_id))
        
#         # Add to batch_students linking table for compatibility
#         cursor.execute("""
#             INSERT INTO batch_students (batch_id, student_id, is_active) 
#             VALUES (%s, %s, TRUE) ON DUPLICATE KEY UPDATE is_active=TRUE
#         """, (batch_id, student_id))
        
#         conn.commit()
#         return jsonify({'success': True, 'message': 'Student successfully enrolled!'})
#     except Exception as e:
#         return jsonify({'success': False, 'message': str(e)})
#     finally:
#         conn.close()


        # --- API: Save Socio-Economic ---
# @admin_bp.route('/api/save_socio', methods=['POST'])
# def save_socio():
#     data = request.json
#     student_id = data.get('student_id')
    
#     # Handle checkboxes (sent as a list)
#     assets = ",".join(data.get('assets', []))
    
#     conn = current_app.get_db_connection()
#     cursor = conn.cursor()
#     try:
#         cursor.execute("""
#             INSERT INTO student_socio_economic 
#             (student_id, housing_type, housing_condition, room_count, 
#              lighting_source, cooking_fuel, water_source, household_assets, family_members_count)
#             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
#             ON DUPLICATE KEY UPDATE 
#             housing_type=VALUES(housing_type),
#             cooking_fuel=VALUES(cooking_fuel),
#             water_source=VALUES(water_source),
#             household_assets=VALUES(household_assets)
#         """, (student_id, data.get('housing_type'), data.get('housing_condition'), 
#               data.get('room_count'), data.get('lighting_source'),
#               data.get('cooking_fuel'), data.get('water_source'), assets, data.get('family_members_count')))
        
#         conn.commit()
#         return jsonify({'success': True})
#     except Exception as e:
#         return jsonify({'success': False, 'message': str(e)})
#     finally:
#         conn.close()

# --- API: Save Socio ---
@admin_bp.route('/api/save_socio', methods=['POST'])
def save_socio():
    data = request.json
    student_id = data.get('student_id')
    assets = ",".join(data.get('assets', [])) # Convert list to string
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        # Upsert Logic
        cursor.execute("""
            INSERT INTO student_socio_economic (student_id, housing_type, housing_condition, room_count, lighting_source, cooking_fuel, water_source, household_assets, family_members_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            housing_type=VALUES(housing_type), housing_condition=VALUES(housing_condition), room_count=VALUES(room_count), 
            lighting_source=VALUES(lighting_source), cooking_fuel=VALUES(cooking_fuel), water_source=VALUES(water_source),
            household_assets=VALUES(household_assets), family_members_count=VALUES(family_members_count)
        """, (student_id, data.get('housing_type'), data.get('housing_condition'), data.get('room_count'), 
              data.get('lighting_source'), data.get('cooking_fuel'), data.get('water_source'), assets, data.get('family_members_count')))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# --- ROUTE: PDF Download ---
@admin_bp.route('/download_student_pdf/<int:student_id>')
def download_student_pdf(student_id):
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch all data (Similar to manage_student)
    cursor.execute("SELECT s.*, u.full_name, u.email, b.batch_name FROM students s JOIN users u ON s.user_id = u.user_id LEFT JOIN batches b ON s.batch_id = b.batch_id WHERE s.student_id = %s", (student_id,))
    student = cursor.fetchone()
    cursor.execute("SELECT * FROM student_personal_details WHERE student_id = %s", (student_id,))
    basic = cursor.fetchone()
    cursor.execute("SELECT * FROM student_socio_economic WHERE student_id = %s", (student_id,))
    socio = cursor.fetchone()
    conn.close()

    html = render_template('admin/pdf_report.html', student=student, basic=basic, socio=socio)
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)
    
    if pisa_status.err: return "PDF Error"
    
    pdf_buffer.seek(0)
    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={student["full_name"]}_Profile.pdf'
    return response



# --- API: Save Experience ---
@admin_bp.route('/api/save_experience', methods=['POST'])
def save_experience():
    data = request.json
    student_id = data.get('student_id')
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO student_experience (student_id, exp_type, employer_name, designation, salary, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (student_id, data.get('exp_type'), data.get('employer'), data.get('designation'), 
              data.get('salary') or 0, data.get('start_date') or None, data.get('end_date') or None))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# --- API: Save Counselling ---
@admin_bp.route('/api/save_counselling', methods=['POST'])
def save_counselling():
    data = request.json
    student_id = data.get('student_id')
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO student_counselling (student_id, interest_inventory, status, counsellor_1_rating, 
                                           recommended_course, counsellor_1_comments, parent_counselling_comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE status=VALUES(status)
        """, (student_id, data.get('interest'), data.get('status'), data.get('rating'),
              data.get('rec_course'), data.get('comments'), data.get('parent_comments')))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# --- API: Upload Document ---
@admin_bp.route('/api/upload_document', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'})
    
    file = request.files['file']
    student_id = request.form.get('student_id')
    doc_type = request.form.get('doc_type')
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})

    if file:
        filename = secure_filename(f"{student_id}_{doc_type}_{file.filename}")
        # Ensure directory exists
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'documents')
        os.makedirs(upload_folder, exist_ok=True)
        
        file.save(os.path.join(upload_folder, filename))
        file_path = f"uploads/documents/{filename}"

        conn = current_app.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO student_documents (student_id, doc_type, file_path) VALUES (%s, %s, %s)", 
                           (student_id, doc_type, file_path))
            doc_id = cursor.lastrowid
            conn.commit()
            return jsonify({'success': True, 'doc_id': doc_id, 'file_url': url_for('static', filename=file_path)})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
        finally:
            conn.close()

# --- API: Delete Document ---
@admin_bp.route('/api/delete_document', methods=['POST'])
def delete_document():
    doc_id = request.json.get('doc_id')
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM student_documents WHERE id = %s", (doc_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# --- API: Save Placement ---
@admin_bp.route('/api/save_placement', methods=['POST'])
def save_placement():
    data = request.json
    student_id = data.get('student_id')
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO student_placement (student_id, interview_status, remarks)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE interview_status=VALUES(interview_status)
        """, (student_id, data.get('status'), data.get('remarks')))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@admin_bp.route('/api/finalize_enrollment', methods=['POST'])
def finalize_enrollment():
    data = request.json
    student_id = data.get('student_id')
    batch_id = data.get('batch_id')
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Get Batch Info
        cursor.execute("SELECT course_id, start_date, batch_name FROM batches WHERE batch_id = %s", (batch_id,))
        batch = cursor.fetchone()
        if not batch: return jsonify({'success': False, 'message': 'Invalid Batch'})

        # 2. Check 7-Day Rule
        start_date = batch['start_date'] # Ensure this is a date object
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
        days_passed = (datetime.now().date() - start_date).days
        
        if days_passed > 7:
            # --- LATE ENROLLMENT FLOW ---
            reason = f"Late joining for {batch['batch_name']}. Batch started {days_passed} days ago."
            
            # Store the intended batch_id in payload so Super Admin can apply it later
            payload = json.dumps({"batch_id": batch_id, "course_id": batch['course_id']})
            
            cursor.execute("""
                INSERT INTO approval_requests (requester_id, action_type, target_id, reason, status, new_data_payload)
                VALUES (%s, 'LATE_ENROLLMENT', %s, %s, 'PENDING', %s)
            """, (current_user.user_id, student_id, reason, payload))
            
            # Set status to pending
            cursor.execute("UPDATE students SET enrollment_status = 'PENDING_APPROVAL' WHERE student_id = %s", (student_id,))
            conn.commit()
            
            return jsonify({'success': True, 'message': f'Batch started >7 days ago. Approval request sent.'})

        # 3. NORMAL FLOW (Same as before)
        # Generate ID
        new_id = f"MIT-{datetime.now().year}-{student_id}"
        
        cursor.execute("""
            UPDATE students SET batch_id=%s, course_id=%s, enrollment_status='ENROLLED', enrollment_id=%s 
            WHERE student_id=%s
        """, (batch_id, batch['course_id'], new_id, student_id))
        
        cursor.execute("""
            INSERT INTO batch_students (batch_id, student_id, is_active) 
            VALUES (%s, %s, TRUE) ON DUPLICATE KEY UPDATE is_active=TRUE
        """, (batch_id, student_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Enrollment Successful!'})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()



# --- VIEW: Manage Student (Edit Mode) ---
# @admin_bp.route('/manage_student/<int:student_id>')
# def manage_student(student_id):
#     conn = current_app.get_db_connection()
#     cursor = conn.cursor(dictionary=True)
    
#     # Fetch all data sections
#     cursor.execute("SELECT s.*, b.batch_name FROM students s LEFT JOIN batches b ON s.batch_id = b.batch_id WHERE s.student_id = %s", (student_id,))
#     student = cursor.fetchone()
    
#     cursor.execute("SELECT * FROM student_personal_details WHERE student_id = %s", (student_id,))
#     basic = cursor.fetchone() or {}
    
#     cursor.execute("SELECT * FROM student_socio_economic WHERE student_id = %s", (student_id,))
#     socio = cursor.fetchone() or {}
    
#     cursor.execute("SELECT * FROM student_education WHERE student_id = %s", (student_id,))
#     education = cursor.fetchall()
    
#     cursor.execute("SELECT * FROM student_family WHERE student_id = %s", (student_id,))
#     family = cursor.fetchall()
    
#     cursor.execute("SELECT * FROM student_experience WHERE student_id = %s", (student_id,))
#     experience = cursor.fetchone() or {}
    
#     cursor.execute("SELECT * FROM student_counselling WHERE student_id = %s", (student_id,))
#     counselling = cursor.fetchone() or {}
    
#     cursor.execute("SELECT * FROM student_documents WHERE student_id = %s", (student_id,))
#     documents = cursor.fetchall()
    
#     cursor.execute("SELECT * FROM student_placement WHERE student_id = %s", (student_id,))
#     placement = cursor.fetchone() or {}

#     cursor.execute("SELECT batch_id, batch_name FROM batches WHERE is_active = TRUE")
#     batches = cursor.fetchall()
#     conn.close()
    
#     return render_template('admin/add_student.html', 
#                            mode='edit', student_id=student_id, student=student,
#                            basic=basic, socio=socio, education=education,
#                            family=family, experience=experience, 
#                            counselling=counselling, documents=documents,
#                            placement=placement, batches=batches)


@admin_bp.route('/request_student_dropout/<int:student_id>', methods=['POST'])
def request_student_dropout(student_id):
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Get details for the request message
        cursor.execute("""
            SELECT u.full_name, u.user_id 
            FROM students s JOIN users u ON s.user_id = u.user_id 
            WHERE s.student_id = %s
        """, (student_id,))
        student = cursor.fetchone()
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found.'})

        # Check if already requested
        cursor.execute("""
            SELECT request_id FROM approval_requests 
            WHERE target_id = %s AND action_type = 'DROPOUT' AND status = 'PENDING'
        """, (student_id,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'A dropout request is already pending for this student.'})

        # Create Request
        reason = f"Admin requested dropout for {student['full_name']}."
        cursor.execute("""
            INSERT INTO approval_requests (requester_id, action_type, target_id, reason, status) 
            VALUES (%s, 'DROPOUT', %s, %s, 'PENDING')
        """, (current_user.user_id, student_id, reason))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Dropout request sent to Super Admin.'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@admin_bp.route('/download_batch_report/<int:batch_id>/<string:report_type>')
def download_batch_report(batch_id, report_type):
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Define status based on report type
    status_filter = 'DROPOUT' if report_type == 'dropout' else 'ALUMNI'
    
    cursor.execute("""
        SELECT u.full_name, u.email, u.phone, s.enrollment_id, s.enrollment_status
        FROM students s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.batch_id = %s AND s.enrollment_status = %s
    """, (batch_id, status_filter))
    students = cursor.fetchall()
    
    cursor.execute("SELECT batch_name FROM batches WHERE batch_id = %s", (batch_id,))
    batch_name = cursor.fetchone()['batch_name']
    conn.close()

    # Generate CSV
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Enrollment ID', 'Name', 'Email', 'Phone', 'Status']) # Header
    
    for s in students:
        cw.writerow([s['enrollment_id'], s['full_name'], s['email'], s['phone'], s['enrollment_status']])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={batch_name}_{report_type}_list.csv"
    output.headers["Content-type"] = "text/csv"
    return output


# --- VIEW: Manage Student (Edit Mode) - FIXED NAME LOADING ---
@admin_bp.route('/manage_student/<int:student_id>')
def manage_student(student_id):
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch Master Data + User Name + Profile Pic
    cursor.execute("""
        SELECT s.*, b.batch_name, u.first_name, u.last_name, u.profile_picture 
        FROM students s 
        JOIN users u ON s.user_id = u.user_id
        LEFT JOIN batches b ON s.batch_id = b.batch_id 
        WHERE s.student_id = %s
    """, (student_id,))
    student = cursor.fetchone()
    
    # 2. Fetch Details
    cursor.execute("SELECT * FROM student_personal_details WHERE student_id = %s", (student_id,))
    basic = cursor.fetchone() or {}
    
    # If basic details table is empty/partial, fallback to user table for names
    if student:
        if 'first_name' not in basic or not basic['first_name']: basic['first_name'] = student['first_name']
        if 'last_name' not in basic or not basic['last_name']: basic['last_name'] = student['last_name']

    cursor.execute("SELECT * FROM student_socio_economic WHERE student_id = %s", (student_id,))
    socio = cursor.fetchone() or {}
    
    cursor.execute("SELECT * FROM student_education WHERE student_id = %s", (student_id,))
    education = cursor.fetchall()
    
    cursor.execute("SELECT * FROM student_family WHERE student_id = %s", (student_id,))
    family = cursor.fetchall()
    
    cursor.execute("SELECT * FROM student_experience WHERE student_id = %s", (student_id,))
    experience = cursor.fetchone() or {}
    
    cursor.execute("SELECT * FROM student_counselling WHERE student_id = %s", (student_id,))
    counselling = cursor.fetchone() or {}
    
    cursor.execute("SELECT * FROM student_documents WHERE student_id = %s", (student_id,))
    documents = cursor.fetchall()
    
    cursor.execute("SELECT * FROM student_placement WHERE student_id = %s", (student_id,))
    placement = cursor.fetchone() or {}

    cursor.execute("SELECT batch_id, batch_name FROM batches WHERE is_active = TRUE")
    batches = cursor.fetchall()
    conn.close()
    
    return render_template('admin/add_student.html', 
                           mode='edit', student_id=student_id, student=student,
                           basic=basic, socio=socio, education=education,
                           family=family, experience=experience, 
                           counselling=counselling, documents=documents,
                           placement=placement, batches=batches)