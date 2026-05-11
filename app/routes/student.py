from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from app.utils.helpers import get_user_stats
from app.tasks import evaluate_submission
from app.utils.validators import validate_date_range,validate_leave_dates
import mysql.connector
from datetime import datetime, timedelta
import os
import io




student_bp = Blueprint('student', __name__)

@student_bp.before_request
def restrict_to_student():
    if not current_user.is_authenticated or current_user.role != 'student':
        flash('Access denied. Student privileges required.', 'danger')
        return redirect(url_for('auth.login'))
    

def log_activity(user_id, action, table_affected, record_id, description):
        """Helper function to log student activities."""
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



# @student_bp.route('/dashboard')
# def dashboard():
#     stats = get_user_stats(current_user.user_id, 'student')
#     conn = current_app.get_db_connection()
#     upcoming_assignments = []
#     recent_feedback = []
#     chart_data = {}

#     if not conn:
#         flash('Database connection error.', 'danger')
#         return render_template('student/dashboard.html', stats=stats, upcoming_assignments=[], recent_feedback=[], chart_data={})

#     try:
#         cursor = conn.cursor(dictionary=True)
        
#         cursor.execute("""
#             SELECT s.student_id, bs.batch_id
#             FROM students s
#             LEFT JOIN batch_students bs ON s.student_id = bs.student_id AND bs.is_active = TRUE
#             WHERE s.user_id = %s
#         """, (current_user.user_id,))
#         student_data = cursor.fetchone()
        
#         if student_data:
#             student_id = student_data['student_id']
#             batch_id = student_data['batch_id']

#             # --- Fetch Data for Actionable Lists ---
#             if batch_id:
#                 cursor.execute("""
#                     SELECT a.title, a.due_date, t.topic_name
#                     FROM assignments a
#                     JOIN topics t ON a.topic_id = t.topic_id
#                     WHERE a.batch_id = %s AND a.due_date >= NOW() AND a.is_active = TRUE
#                     AND a.assignment_id NOT IN (SELECT assignment_id FROM assignment_submissions WHERE student_id = %s)
#                     ORDER BY a.due_date ASC
#                     LIMIT 5
#                 """, (batch_id, student_id))
#                 upcoming_assignments = cursor.fetchall()
            
#             cursor.execute("""
#                 SELECT a.title, asub.grade, asub.feedback, asub.graded_at
#                 FROM assignment_submissions asub
#                 JOIN assignments a ON asub.assignment_id = a.assignment_id
#                 WHERE asub.student_id = %s AND asub.grade IS NOT NULL
#                 ORDER BY asub.graded_at DESC
#                 LIMIT 5
#             """, (student_id,))
#             recent_feedback = cursor.fetchall()

#             # --- Fetch Data for Charts ---
#             # Chart 1: Grade Trajectory (Line Chart)
#             cursor.execute("""
#                 SELECT a.title, asub.grade
#                 FROM assignment_submissions asub
#                 JOIN assignments a ON asub.assignment_id = a.assignment_id
#                 WHERE asub.student_id = %s AND asub.grade IS NOT NULL
#                 ORDER BY a.due_date ASC
#             """, (student_id,))
#             grades = cursor.fetchall()
#             chart_data['grade_trajectory'] = {
#                 'labels': [g['title'] for g in grades],
#                 'data': [g['grade'] for g in grades]
#             }

#             # Chart 2: Performance by Topic (Radar Chart)
#             cursor.execute("""
#                 SELECT t.topic_name, AVG(asub.grade) as avg_grade
#                 FROM assignment_submissions asub
#                 JOIN assignments a ON asub.assignment_id = a.assignment_id
#                 JOIN topics t ON a.topic_id = t.topic_id
#                 WHERE asub.student_id = %s AND asub.grade IS NOT NULL
#                 GROUP BY t.topic_id, t.topic_name
#             """, (student_id,))
#             topic_grades = cursor.fetchall()
#             chart_data['topic_performance'] = {
#                 'labels': [tg['topic_name'] for tg in topic_grades],
#                 'data': [round(tg['avg_grade'], 1) if tg['avg_grade'] else 0 for tg in topic_grades]
#             }
        
#     except mysql.connector.Error as err:
#         flash(f'Error retrieving dashboard data: {err}', 'danger')
#         print(f"Student Dashboard Error: {err}")
#     finally:
#         if conn and conn.is_connected():
#             cursor.close()
#             conn.close()
    
#     return render_template('student/dashboard.html', 
#                          stats=stats, 
#                          upcoming_assignments=upcoming_assignments,
#                          recent_feedback=recent_feedback,
#                          chart_data=chart_data,
#                          now=datetime.now())


@student_bp.route('/dashboard')
def dashboard():
    stats = get_user_stats(current_user.user_id, 'student')
    conn = current_app.get_db_connection()
    upcoming_assignments = []
    recent_feedback = []
    chart_data = {}

    if not conn:
        flash('Database connection error.', 'danger')
        return render_template('student/dashboard.html', stats=stats, upcoming_assignments=[], recent_feedback=[], chart_data={})

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get Student ID and Batch info
        cursor.execute("""
            SELECT s.student_id, bs.batch_id
            FROM students s
            LEFT JOIN batch_students bs ON s.student_id = bs.student_id AND bs.is_active = TRUE
            WHERE s.user_id = %s
        """, (current_user.user_id,))
        student_data = cursor.fetchone()
        
        if student_data:
            student_id = student_data['student_id']
            batch_id = student_data['batch_id']

            # --- FIX: Recalculate Average Grade Explicitly (Manual + Auto) ---
            # This ensures the KPI card is accurate regardless of what get_user_stats returns
            cursor.execute("""
                SELECT AVG(
                    CASE 
                        WHEN grade IS NOT NULL THEN grade 
                        WHEN auto_grade IS NOT NULL THEN auto_grade
                        ELSE NULL 
                    END
                ) as real_average
                FROM assignment_submissions 
                WHERE student_id = %s AND (grade IS NOT NULL OR auto_grade IS NOT NULL)
            """, (student_id,))
            avg_result = cursor.fetchone()
            
            # Update the stats dictionary
            if avg_result and avg_result['real_average'] is not None:
                stats['average_grade'] = round(float(avg_result['real_average']), 1)
            else:
                stats['average_grade'] = 0

            # --- Fetch Data for Actionable Lists ---
            if batch_id:
                cursor.execute("""
                    SELECT a.title, a.due_date, t.topic_name
                    FROM assignments a
                    JOIN topics t ON a.topic_id = t.topic_id
                    WHERE a.batch_id = %s AND a.due_date >= NOW() AND a.is_active = TRUE
                    AND a.assignment_id NOT IN (SELECT assignment_id FROM assignment_submissions WHERE student_id = %s)
                    ORDER BY a.due_date ASC
                    LIMIT 5
                """, (batch_id, student_id))
                upcoming_assignments = cursor.fetchall()
            
            # Updated to show Auto Grade if Manual Grade is missing
            cursor.execute("""
                SELECT a.title, 
                       COALESCE(asub.grade, asub.auto_grade) as grade, 
                       asub.feedback, asub.auto_feedback, asub.graded_at, asub.evaluation_status
                FROM assignment_submissions asub
                JOIN assignments a ON asub.assignment_id = a.assignment_id
                WHERE asub.student_id = %s AND (asub.grade IS NOT NULL OR asub.auto_grade IS NOT NULL)
                ORDER BY asub.graded_at DESC
                LIMIT 5
            """, (student_id,))
            recent_feedback = cursor.fetchall()

            # --- Fetch Data for Charts ---
            
            # Chart 1: Grade Trajectory (Line Chart) - FIXED to include Auto Grades
            cursor.execute("""
                SELECT a.title, 
                       COALESCE(asub.grade, asub.auto_grade) as grade
                FROM assignment_submissions asub
                JOIN assignments a ON asub.assignment_id = a.assignment_id
                WHERE asub.student_id = %s AND (asub.grade IS NOT NULL OR asub.auto_grade IS NOT NULL)
                ORDER BY a.due_date ASC
            """, (student_id,))
            grades = cursor.fetchall()
            chart_data['grade_trajectory'] = {
                'labels': [g['title'] for g in grades],
                'data': [g['grade'] for g in grades]
            }

            # Chart 2: Performance by Topic (Radar Chart) - FIXED to include Auto Grades
            cursor.execute("""
                SELECT t.topic_name, 
                       AVG(COALESCE(asub.grade, asub.auto_grade)) as avg_grade
                FROM assignment_submissions asub
                JOIN assignments a ON asub.assignment_id = a.assignment_id
                JOIN topics t ON a.topic_id = t.topic_id
                WHERE asub.student_id = %s AND (asub.grade IS NOT NULL OR asub.auto_grade IS NOT NULL)
                GROUP BY t.topic_id, t.topic_name
            """, (student_id,))
            topic_grades = cursor.fetchall()
            chart_data['topic_performance'] = {
                'labels': [tg['topic_name'] for tg in topic_grades],
                'data': [round(tg['avg_grade'], 1) if tg['avg_grade'] else 0 for tg in topic_grades]
            }
        
    except mysql.connector.Error as err:
        flash(f'Error retrieving dashboard data: {err}', 'danger')
        print(f"Student Dashboard Error: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    
    return render_template('student/dashboard.html', 
                         stats=stats, 
                         upcoming_assignments=upcoming_assignments,
                         recent_feedback=recent_feedback,
                         chart_data=chart_data,
                         now=datetime.now())
# __________________________________________________________-
# ===============================================================
# ASSIGNMENTS VIEW (Updated to pass student_comments)
# ===============================================================
@student_bp.route('/assignments')
@login_required
def assignments():
    conn = current_app.get_db_connection()
    assignments = []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # CORRECTED QUERY: Fetches submission_text and not the non-existent student_comments
            cursor.execute("""
                SELECT
                    a.*, t.topic_name,
                    asub.submission_id, asub.submitted_at, asub.grade, asub.auto_grade,
                    asub.feedback, asub.auto_feedback, asub.evaluation_status,
                    asub.submission_text,
                    asub.file_path AS submission_file, asub.is_late,
                    CASE
                        WHEN asub.grade IS NOT NULL OR asub.auto_grade IS NOT NULL THEN 'Graded'
                        WHEN asub.evaluation_status = 'processing' THEN 'Processing'
                        WHEN asub.submission_id IS NOT NULL THEN 'Submitted'
                        ELSE 'Pending'
                    END AS status
                FROM assignments a
                JOIN topics t ON a.topic_id = t.topic_id
                JOIN batch_students bs ON a.batch_id = bs.batch_id
                LEFT JOIN assignment_submissions asub ON a.assignment_id = asub.assignment_id AND asub.student_id = bs.student_id
                WHERE bs.student_id = %s AND a.is_active = TRUE
                ORDER BY a.due_date DESC;
            """, (current_user.student_id,))
            assignments = cursor.fetchall()
        except mysql.connector.Error as err:
            flash(f'Error retrieving assignments: {err}', 'danger')
            # Print the error to the console for easier debugging
            print(f"ASSIGNMENT PAGE QUERY ERROR: {err}")
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('student/assignments.html', assignments=assignments)


# ===============================================================
# ASSIGNMENT SUBMISSION (Corrected to use submission_text)
# ===============================================================
@student_bp.route('/submit_assignment/<int:assignment_id>', methods=['POST'])
@login_required
def submit_assignment(assignment_id):
    # Get the student's text comment from the form
    student_comment = request.form.get('student_comments', '')
    
    # Check for the uploaded file
    if 'submission_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part in the request.'})
    file = request.files['submission_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Please select a solution file to upload.'})

    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'})
        
    try:
        cursor = conn.cursor(dictionary=True)
        student_id = current_user.student_id
        
        cursor.execute("SELECT evaluation_type, due_date FROM assignments WHERE assignment_id = %s", (assignment_id,))
        assignment_data = cursor.fetchone()
        if not assignment_data:
            return jsonify({'success': False, 'message': 'Assignment not found.'})

        is_late = datetime.now() > assignment_data['due_date'] if assignment_data['due_date'] else False
        
        # Save the uploaded file
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'submissions')
        os.makedirs(upload_dir, exist_ok=True)
        _, file_extension = os.path.splitext(file.filename)
        unique_filename = f"submission_{assignment_id}_{student_id}_{int(datetime.now().timestamp())}{file_extension}"
        file_path_full = os.path.join(upload_dir, unique_filename)
        file.save(file_path_full)
        file_path_relative = os.path.join('uploads', 'submissions', unique_filename).replace("\\", "/")
        
        # Use INSERT ... ON DUPLICATE KEY to save both the comment and the file path
        cursor.execute("""
            INSERT INTO assignment_submissions (assignment_id, student_id, submission_text, file_path, is_late, submitted_at, evaluation_status) 
            VALUES (%s, %s, %s, %s, %s, NOW(), %s)
            ON DUPLICATE KEY UPDATE 
            submission_text = VALUES(submission_text), 
            file_path = VALUES(file_path), 
            is_late = VALUES(is_late), 
            submitted_at = NOW(),
            evaluation_status = VALUES(evaluation_status), 
            grade = NULL, auto_grade = NULL, feedback = NULL, auto_feedback = NULL
        """, (assignment_id, student_id, student_comment, file_path_relative, is_late, 'pending'))
        
        cursor.execute("SELECT submission_id FROM assignment_submissions WHERE assignment_id = %s AND student_id = %s", (assignment_id, student_id))
        submission_id = cursor.fetchone()['submission_id']

        if assignment_data.get('evaluation_type', 'none') != 'none':
            evaluate_submission.delay(submission_id)
            message = 'Assignment submitted! It is now queued for auto-evaluation.'
        else:
            message = 'Assignment submitted successfully!'
        
        conn.commit()
        log_activity(current_user.user_id, 'submit', 'assignment_submissions', submission_id, f"Submitted assignment ID: {assignment_id}")
        return jsonify({'success': True, 'message': message})

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn and conn.is_connected(): conn.close()





# _______________________________________________
@student_bp.route('/leave_management')
@login_required
def leave_management():
    conn = current_app.get_db_connection()
    leave_applications, leave_types, student_info = [], [], {}
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT s.student_id, bs.batch_id, b.batch_name FROM students s
                JOIN batch_students bs ON s.student_id = bs.student_id AND bs.is_active = TRUE
                JOIN batches b ON bs.batch_id = b.batch_id
                WHERE s.user_id = %s
            """, (current_user.user_id,))
            student_info = cursor.fetchone()

            if student_info:
                cursor.execute("SELECT leave_type_id, type_name FROM leave_types ORDER BY type_name")
                leave_types = cursor.fetchall()
                
                cursor.execute("""
                    SELECT la.*, lt.type_name, b.batch_name FROM leave_applications la
                    LEFT JOIN leave_types lt ON la.leave_type_id = lt.leave_type_id
                    LEFT JOIN batches b ON la.batch_id = b.batch_id
                    WHERE la.student_id = %s 
                    ORDER BY la.applied_at DESC
                """, (student_info['student_id'],))
                leave_applications = cursor.fetchall()
                
                # This call now works because of the fix in models.py
                student_info['balances'] = current_user.get_all_leave_balances_for_batch(student_info['batch_id'])
        except mysql.connector.Error as err:
            flash(f'Error retrieving leave data: {err}', 'danger')
        finally:
            if conn.is_connected(): conn.close()
    
    return render_template('student/leave_application.html', 
                           leave_applications=leave_applications, 
                           leave_types=leave_types, # This is the key part that was missing
                           student_info=student_info,
                           now=datetime.now())

# ___________________________________-

@student_bp.route('/apply_leave', methods=['POST'])
@login_required
def apply_leave():
    # This route will now handle FormData for the file upload
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    reason = request.form.get('reason')
    leave_type_id = request.form.get('leave_type_id', type=int)
    batch_id = request.form.get('batch_id', type=int)
    
    student_id = current_user.student_id

    # Server-side validation using our robust validator
    is_valid, message = validate_leave_dates(start_date, end_date, leave_type_id, student_id, batch_id)
    if not is_valid:
        return jsonify({'success': False, 'message': message})
    
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'})

    try:
        cursor = conn.cursor()
        
        # Calculate leave days (excluding weekends)
        s_date = datetime.strptime(start_date, '%Y-%m-%d')
        e_date = datetime.strptime(end_date, '%Y-%m-%d')
        days_requested = sum(1 for day in range((e_date - s_date).days + 1) if (s_date + timedelta(days=day)).weekday() < 5)

        # Handle file upload
        supporting_document = None
        if 'supporting_document' in request.files:
            file = request.files['supporting_document']
            if file and file.filename != '':
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'documents')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"leave_{student_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                supporting_document = os.path.join('uploads', 'documents', filename).replace("\\", "/")
        
        cursor.execute("""
            INSERT INTO leave_applications (student_id, batch_id, leave_type_id, start_date, end_date, reason, days_requested, supporting_document) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (student_id, batch_id, leave_type_id, start_date, end_date, reason, days_requested, supporting_document))
        leave_id = cursor.lastrowid
        conn.commit()
        
        log_activity(current_user.user_id, 'create', 'leave_applications', leave_id, f"Applied for leave from {start_date} to {end_date}")
        
        return jsonify({'success': True, 'message': 'Leave application submitted successfully'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn.is_connected(): conn.close()
# _________________________




@student_bp.route('/cancel_leave/<int:leave_id>', methods=['POST'])
@login_required
def cancel_leave(leave_id):
    # Check if student owns this leave application
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get student ID
            cursor.execute("SELECT student_id FROM students WHERE user_id = %s", (current_user.user_id,))
            student_data = cursor.fetchone()
            
            if not student_data:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Student record not found'})
            
            student_id = student_data['student_id']
            
            # Check if leave application belongs to student
            cursor.execute("""
                SELECT * FROM leave_applications 
                WHERE leave_id = %s AND student_id = %s AND status = 'pending'
            """, (leave_id, student_id))
            leave_data = cursor.fetchone()
            
            if not leave_data:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Leave application not found or cannot be cancelled'})
            
            # Delete leave application
            cursor.execute("DELETE FROM leave_applications WHERE leave_id = %s", (leave_id,))
            
            conn.commit()
            
            # Log activity
            log_activity(current_user.user_id, 'cancel', 'leave_applications', leave_id, 
                        f"Cancelled leave application from {leave_data['start_date']} to {leave_data['end_date']}")
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Leave application cancelled successfully'})
        except mysql.connector.Error as err:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error cancelling leave application: {err}'})
    
    return jsonify({'success': False, 'message': 'Database connection error'})


@student_bp.route('/profile')
@login_required
def profile():
    conn = current_app.get_db_connection()
    student_data = {}
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # UPDATED QUERY:
            # 1. Replaced 's.enrollment_date' with 's.created_at as enrollment_date'
            # 2. Updated JOINs to go Student -> Batch -> Course (New Schema Logic)
            cursor.execute("""
                SELECT 
                    s.student_id, 
                    s.created_at as enrollment_date,  -- <--- FIXED HERE
                    u.is_active,
                    u.full_name, u.email, u.phone, u.created_at,
                    c.course_name, 
                    b.start_date, b.end_date, b.batch_name
                FROM students s 
                JOIN users u ON s.user_id = u.user_id 
                LEFT JOIN batches b ON s.batch_id = b.batch_id
                LEFT JOIN courses c ON b.course_id = c.course_id
                WHERE s.user_id = %s
            """, (current_user.user_id,))
            
            student_data = cursor.fetchone()

            if student_data and student_data.get('start_date') and student_data.get('end_date'):
                # Safely calculate progress
                total_duration = (student_data['end_date'] - student_data['start_date']).days
                days_completed = (datetime.now().date() - student_data['start_date']).days
                
                if total_duration > 0:
                    percentage = (days_completed / total_duration) * 100
                    # Clamp value between 0 and 100
                    student_data['progress_percentage'] = max(0, min(100, round(percentage)))
                else:
                    student_data['progress_percentage'] = 0
                    
                student_data['days_completed'] = max(0, days_completed)
        
        except mysql.connector.Error as err:
            print(f"Profile Error: {err}")
            flash('Error loading profile.', 'danger')
        finally:
            if conn.is_connected(): conn.close()
            
    return render_template('student/profile.html', student_data=student_data, now=datetime.now())


@student_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    phone = request.form.get('phone')
    
    # Validate input
    if not phone:
        return jsonify({'success': False, 'message': 'Phone number is required'})
    
    from app.utils.validators import validate_phone
    if not validate_phone(phone):
        return jsonify({'success': False, 'message': 'Please enter a valid phone number'})
    
    # Update profile
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET phone = %s WHERE user_id = %s", (phone, current_user.user_id))
            
            conn.commit()
            
            # Log activity
            log_activity(current_user.user_id, 'update', 'users', current_user.user_id, "Updated profile information")
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Profile updated successfully'})
        except mysql.connector.Error as err:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error updating profile: {err}'})
    
    return jsonify({'success': False, 'message': 'Database connection error'})

@student_bp.route('/download_assignment/<int:assignment_id>')
@login_required
def download_assignment(assignment_id):
    # Check if student has access to this assignment
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get student course
            cursor.execute("SELECT course_id FROM students WHERE user_id = %s", (current_user.user_id,))
            student_data = cursor.fetchone()
            
            if not student_data:
                cursor.close()
                conn.close()
                flash('Student record not found', 'danger')
                return redirect(url_for('student.assignments'))
            
            # Check if assignment belongs to student's course
            cursor.execute("""
                SELECT a.*, t.topic_name 
                FROM assignments a 
                JOIN topics t ON a.topic_id = t.topic_id 
                WHERE a.assignment_id = %s AND t.course_id = %s
            """, (assignment_id, student_data['course_id']))
            assignment_data = cursor.fetchone()
            
            if not assignment_data:
                cursor.close()
                conn.close()
                flash('Access denied to this assignment', 'danger')
                return redirect(url_for('student.assignments'))
            
            if not assignment_data['file_path']:
                cursor.close()
                conn.close()
                flash('No file available for this assignment', 'danger')
                return redirect(url_for('student.assignments'))
            
            # Get file path and send file
            file_path = os.path.join(current_app.root_path, assignment_data['file_path'].lstrip('/'))
            
            if os.path.exists(file_path):
                # Log activity
                log_activity(current_user.user_id, 'download', 'assignments', assignment_id, 
                            f"Downloaded assignment: {assignment_data['title']}")
                
                cursor.close()
                conn.close()
                return send_file(file_path, as_attachment=True, download_name=assignment_data['title'] + os.path.splitext(file_path)[1])
            else:
                cursor.close()
                conn.close()
                flash('File not found', 'danger')
                return redirect(url_for('student.assignments'))
            
        except mysql.connector.Error as err:
            flash(f'Error downloading assignment: {err}', 'danger')
            return redirect(url_for('student.assignments'))
    
    flash('Database connection error', 'danger')
    return redirect(url_for('student.assignments'))

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


# ______________________________________________________________________________________________


