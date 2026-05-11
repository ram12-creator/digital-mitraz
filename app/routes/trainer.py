from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from app.utils.helpers import get_user_stats
import mysql.connector
from collections import defaultdict
from datetime import datetime,timedelta

from app.tasks import evaluate_submission 

import os
import io
import csv

trainer_bp = Blueprint('trainer', __name__)




# --- Blueprint Setup and Helper Functions ---
@trainer_bp.before_request
@login_required
def restrict_to_trainer():
    if not current_user.is_authenticated or current_user.role != 'trainer':
        flash('Access denied. Trainer privileges required.', 'danger')
        return redirect(url_for('auth.login'))

def log_activity(user_id, action, table_affected, record_id, description):
    """Helper function to log trainer activities."""
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

def build_topic_tree(topics):
    """Helper function to convert a flat list of topics into a nested tree."""
    # First, initialize every topic with an empty 'children' list.
    for topic in topics:
        topic['children'] = []
    
    # Now, create a map of topic_id to the topic dictionary.
    # All dictionaries in this map now have the 'children' key.
    topic_map = {topic['topic_id']: topic for topic in topics}
    
    tree = []
    for topic in topics:
        if topic.get('parent_topic_id') and topic['parent_topic_id'] in topic_map:
            # If it's a child, append it to its parent's 'children' list.
            parent = topic_map[topic['parent_topic_id']]
            parent['children'].append(topic)
        else:
            # If it has no parent, it's a top-level node in our tree.
            tree.append(topic)
            
    return tree



@trainer_bp.route('/dashboard')
def dashboard():
    stats = get_user_stats(current_user.user_id, 'trainer')
    conn = current_app.get_db_connection()
    
    chart_data = {}
    upcoming_deadlines = []
    
    if not conn:
        flash('Database connection error.', 'danger')
        return render_template('trainer/dashboard.html', stats=stats, chart_data={}, upcoming_deadlines=[])

    try:
        cursor = conn.cursor(dictionary=True)
        
        # --- 1. KPI Cards Data (Unchanged) ---
        cursor.execute("""
            SELECT AVG(asub.grade) as average_grade 
            FROM assignment_submissions asub 
            JOIN assignments a ON asub.assignment_id = a.assignment_id 
            WHERE a.created_by = %s AND asub.grade IS NOT NULL
        """, (current_user.user_id,))
        avg_grade_result = cursor.fetchone()
        stats['average_grade'] = round(avg_grade_result['average_grade'], 1) if avg_grade_result and avg_grade_result['average_grade'] else 0

        # --- 2. The Master Query for the Interactive Dashboard ---
        # This query gets all necessary performance data in one go for the frontend.
        cursor.execute("""
            SELECT 
                s.student_id,
                u.full_name as student_name,
                b.batch_name,
                t.topic_name,
                asub.grade,
                asub.submitted_at,
                (SELECT AVG(att.is_present) * 100 FROM attendance att WHERE att.student_id = s.student_id) as attendance
            FROM students s
            JOIN users u ON s.user_id = u.user_id
            LEFT JOIN assignment_submissions asub ON s.student_id = asub.student_id
            LEFT JOIN assignments a ON asub.assignment_id = a.assignment_id
            LEFT JOIN batches b ON a.batch_id = b.batch_id
            LEFT JOIN topics t ON a.topic_id = t.topic_id
            WHERE a.created_by = %s AND asub.grade IS NOT NULL
        """, (current_user.user_id,))
        chart_data['all_student_data'] = cursor.fetchall()

        # --- 3. Pre-process data for non-interactive or complex charts ---
        
        # Data for Grading Progress (Donut Chart)
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN asub.grade IS NOT NULL THEN 1 ELSE 0 END) as graded,
                SUM(CASE WHEN asub.submission_id IS NOT NULL AND asub.grade IS NULL THEN 1 ELSE 0 END) as ungraded
            FROM assignment_submissions asub
            JOIN assignments a ON asub.assignment_id = a.assignment_id
            WHERE a.created_by = %s
        """, (current_user.user_id,))
        grading_status = cursor.fetchone()
        chart_data['grading_progress'] = [int(grading_status['graded'] or 0), int(grading_status['ungraded'] or 0)]
        
        # Data for Weekly Submission Rhythm (Polar Area Chart)
        submission_rhythm = [0] * 7  # Index 0 = Monday, 6 = Sunday
        if chart_data.get('all_student_data'):
            for record in chart_data['all_student_data']:
                if record['submitted_at']:
                    day_of_week = record['submitted_at'].weekday() # Monday = 0
                    submission_rhythm[day_of_week] += 1
        chart_data['submission_rhythm'] = submission_rhythm

        # Data for Batch Leaderboard (Horizontal Bar Chart)
        cursor.execute("""
            SELECT b.batch_name, AVG(asub.grade) as avg_grade
            FROM assignment_submissions asub
            JOIN assignments a ON asub.assignment_id = a.assignment_id
            JOIN batches b ON a.batch_id = b.batch_id
            WHERE a.created_by = %s AND asub.grade IS NOT NULL
            GROUP BY b.batch_id
            ORDER BY avg_grade DESC
            LIMIT 5
        """, (current_user.user_id,))
        chart_data['batch_leaderboard'] = cursor.fetchall()
        
        # --- 4. Upcoming Deadlines (Unchanged) ---
        cursor.execute("""
            SELECT a.title, b.batch_name, a.due_date,
                   (SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = a.assignment_id) as submissions,
                   (SELECT COUNT(*) FROM batch_students WHERE batch_id = a.batch_id AND is_active = TRUE) as total_students
            FROM assignments a
            JOIN batches b ON a.batch_id = b.batch_id
            WHERE a.created_by = %s AND a.due_date >= NOW() AND a.due_date <= DATE_ADD(NOW(), INTERVAL 7 DAY)
            ORDER BY a.due_date ASC
            LIMIT 5
        """, (current_user.user_id,))
        upcoming_deadlines = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f'Error retrieving dashboard data: {err}', 'danger')
        print(f"Dashboard Error: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    return render_template('trainer/dashboard.html', 
                           stats=stats, 
                           chart_data=chart_data,
                           upcoming_deadlines=upcoming_deadlines,
                           now=datetime.now())

# ____________________________________________



@trainer_bp.route('/my_batches')
@login_required
def my_batches():
    conn = current_app.get_db_connection()
    batches = []
    if not conn:
        flash('Database connection error.', 'danger')
        return render_template('trainer/my_batches.html', batches=[])
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT b.*, c.course_name, COUNT(bs.student_id) as student_count
            FROM batches b 
            JOIN courses c ON b.course_id = c.course_id
            JOIN course_trainers ct ON b.course_id = ct.course_id
            LEFT JOIN batch_students bs ON b.batch_id = bs.batch_id AND bs.is_active = TRUE
            WHERE ct.trainer_id = %s AND b.is_active = TRUE
            GROUP BY b.batch_id 
            ORDER BY c.course_name, b.batch_name
        """, (current_user.user_id,))
        batches = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f'Error retrieving your batches: {err}', 'danger')
    finally:
        if conn.is_connected(): conn.close()
    return render_template('trainer/my_batches.html', batches=batches)
# _______________________


# _________________________________-

@trainer_bp.route('/batch/<int:batch_id>')
def manage_batch(batch_id):
    batch, students, assignments, students_on_leave = None, [], [], []
    topics_tree, flat_topics = [], []
    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error', 'danger')
        return redirect(url_for('trainer.my_batches'))
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT b.*, c.course_name FROM batches b JOIN courses c ON b.course_id = c.course_id JOIN course_trainers ct ON b.course_id = ct.course_id WHERE ct.trainer_id = %s AND b.batch_id = %s", (current_user.user_id, batch_id))
        batch = cursor.fetchone()
        if not batch:
            flash('Access denied or batch not found.', 'danger')
            return redirect(url_for('trainer.my_batches'))

        cursor.execute("SELECT u.full_name, u.email, u.phone FROM users u JOIN students s ON u.user_id = s.user_id JOIN batch_students bs ON s.student_id = bs.student_id WHERE bs.batch_id = %s AND bs.is_active = TRUE ORDER BY u.full_name", (batch_id,))
        students = cursor.fetchall()
        
        cursor.execute("SELECT a.*, t.topic_name FROM assignments a JOIN topics t ON a.topic_id = t.topic_id WHERE a.batch_id = %s ORDER BY a.due_date DESC", (batch_id,))
        assignments = cursor.fetchall()

        cursor.execute("SELECT * FROM topics WHERE batch_id = %s ORDER BY sequence_order, topic_name", (batch_id,))
        flat_topics = cursor.fetchall()
        topics_tree = build_topic_tree(flat_topics)

        cursor.execute("SELECT u.full_name, la.reason FROM leave_applications la JOIN students s ON la.student_id = s.student_id JOIN users u ON s.user_id = u.user_id JOIN batch_students bs ON s.student_id = bs.student_id WHERE bs.batch_id = %s AND la.status = 'approved' AND CURDATE() BETWEEN la.start_date AND la.end_date", (batch_id,))
        students_on_leave = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f'Error loading batch data: {err}', 'danger')
    finally:
        if conn.is_connected(): conn.close()
        
    return render_template('trainer/batch_management.html', batch=batch, students=students, 
                           topics_tree=topics_tree, flat_topics=flat_topics, 
                           assignments=assignments, students_on_leave=students_on_leave,
                           now=datetime.now())

# ______________________________




@trainer_bp.route('/create_topic', methods=['POST'])
@login_required
def create_topic():
    data = request.get_json()
    parent_topic_id = data.get('parent_topic_id')
    if not parent_topic_id:
        parent_topic_id = None

    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO topics (topic_name, description, course_id, trainer_id, sequence_order, batch_id, parent_topic_id) 
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (data.get('topic_name'), data.get('description'), data.get('course_id'), current_user.user_id, data.get('sequence_order'), data.get('batch_id'), parent_topic_id)
        )
        topic_id = cursor.lastrowid
        conn.commit()
        log_activity(current_user.user_id, 'create', 'topics', topic_id, f"Created topic: {data.get('topic_name')}")
        return jsonify({'success': True, 'message': 'Topic created successfully!'})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Database Error: {err}'})
    finally:
        if conn and conn.is_connected(): conn.close()
# ________________


# ____________________________________________



# ________________________________________-


@trainer_bp.route('/get_batches/<int:course_id>')
def get_batches(course_id):
    # This function is fine as-is
    conn = current_app.get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as count FROM course_trainers WHERE trainer_id = %s AND course_id = %s", (current_user.user_id, course_id))
            if cursor.fetchone()['count'] == 0:
                return jsonify({'success': False, 'message': 'Access denied'})
            cursor.execute("SELECT batch_id, batch_name FROM batches WHERE course_id = %s AND is_active = TRUE ORDER BY batch_name", (course_id,))
            batches = cursor.fetchall()
            return jsonify({'success': True, 'batches': batches})
        finally:
            if conn.is_connected(): cursor.close(); conn.close()
    return jsonify({'success': False, 'message': 'Database connection error.'})



# --- AJAX CRUD Endpoints for Topics ---


# ____________________
@trainer_bp.route('/update_topic/<int:topic_id>', methods=['POST'])
def update_topic(topic_id):
    data = request.get_json()
    topic_name, description, sequence_order = data.get('topic_name'), data.get('description'), data.get('sequence_order')
    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE topics SET topic_name=%s, description=%s, sequence_order=%s WHERE topic_id=%s",
                       (topic_name, description, sequence_order, topic_id))
        conn.commit()
        log_activity(current_user.user_id, 'update', 'topics', topic_id, f"Updated topic: {topic_name}")
        return jsonify({'success': True, 'message': 'Topic updated successfully!'})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Database Error: {err}'})
    finally:
        if conn and conn.is_connected(): cursor.close(); conn.close()



@trainer_bp.route('/delete_topic/<int:topic_id>', methods=['POST'])
def delete_topic(topic_id):
    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as count FROM assignments WHERE topic_id = %s", (topic_id,))
        if cursor.fetchone()['count'] > 0:
            return jsonify({'success': False, 'message': 'Cannot delete. This topic has assignments linked to it.'})
        
        cursor.execute("SELECT COUNT(*) as count FROM topics WHERE parent_topic_id = %s", (topic_id,))
        if cursor.fetchone()['count'] > 0:
            return jsonify({'success': False, 'message': 'Cannot delete. This topic has sub-topics. Please delete them first.'})

        cursor.execute("DELETE FROM topics WHERE topic_id = %s", (topic_id,))
        conn.commit()
        log_activity(current_user.user_id, 'delete', 'topics', topic_id, "Deleted a topic")
        return jsonify({'success': True, 'message': 'Topic deleted successfully.'})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Database Error: {err}'})
    finally:
        if conn and conn.is_connected(): conn.close()



# ______________________________

# --- ASSIGNMENT MANAGEMENT ---

@trainer_bp.route('/create_assignment', methods=['POST'])
def create_assignment():
    # This is the updated version that handles test case files
    batch_id = request.form.get('batch_id')
    evaluation_type = request.form.get('evaluation_type', 'none')

    if not batch_id: return jsonify({'success': False, 'message': 'Batch ID is missing.'})

    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO assignments (title, description, topic_id, created_by, due_date, 
                                     assignment_type, max_points, evaluation_type, batch_id) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (request.form.get('title'), request.form.get('description'), request.form.get('topic_id'), 
             current_user.user_id, request.form.get('due_date'), request.form.get('assignment_type'), 
             request.form.get('max_points'), evaluation_type, batch_id)
        )
        assignment_id = cursor.lastrowid
        
        # Handle assignment instruction file
        if 'assignment_file' in request.files:
            file = request.files['assignment_file']
            if file.filename != '':
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'assignments')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"assignment_{assignment_id}_{file.filename}"
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                relative_path = os.path.join('uploads', 'assignments', filename).replace("\\", "/")
                cursor.execute("UPDATE assignments SET file_path = %s WHERE assignment_id = %s", (relative_path, assignment_id))

        # Handle test case file
        if 'test_case_file' in request.files:
            file = request.files['test_case_file']
            if file.filename != '':
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'test_cases')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"testcase_{assignment_id}_{file.filename}"
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                relative_path = os.path.join('uploads', 'test_cases', filename).replace("\\", "/")
                cursor.execute("UPDATE assignments SET test_case_file_path = %s WHERE assignment_id = %s", (relative_path, assignment_id))
        
        conn.commit()
        log_activity(current_user.user_id, 'create', 'assignments', assignment_id, f"Created assignment: {request.form.get('title')}")
        return jsonify({'success': True, 'message': 'Assignment created successfully!'})
    except mysql.connector.Error as err:
        conn.rollback(); return jsonify({'success': False, 'message': f'Database Error: {err}'})
    finally:
        if conn and conn.is_connected(): conn.close()



# ____________________________
@trainer_bp.route('/assignments')
def assignment_management():
    conn = current_app.get_db_connection()
    assignments = []
    topics = [] # Needed for the "Create Assignment" modal

    if not conn:
        flash('Database connection error.', 'danger')
        return render_template('trainer/assignment_management.html', assignments=[], topics=[])

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Fetch all assignments created by this trainer
        cursor.execute("""
            SELECT 
                a.*, 
                t.topic_name, 
                c.course_name
            FROM assignments a
            JOIN topics t ON a.topic_id = t.topic_id
            JOIN courses c ON t.course_id = c.course_id
            WHERE a.created_by = %s
            ORDER BY a.due_date DESC
        """, (current_user.user_id,))
        assignments = cursor.fetchall()

        # Fetch all topics this trainer can assign to
        cursor.execute("""
            SELECT t.topic_id, t.topic_name, c.course_name
            FROM topics t
            JOIN courses c ON t.course_id = c.course_id
            JOIN course_trainers ct ON t.course_id = ct.course_id
            WHERE ct.trainer_id = %s
            ORDER BY c.course_name, t.topic_name
        """, (current_user.user_id,))
        topics = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f'Error retrieving assignment data: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

    return render_template('trainer/assignment_management.html', assignments=assignments, topics=topics)

# ______________________________________-

    
@trainer_bp.route('/submissions/<int:assignment_id>')
def view_submissions(assignment_id):
    conn = current_app.get_db_connection()
    assignment, submissions = None, []
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # Security check: Ensure the trainer has access to this assignment
            cursor.execute("""
                SELECT a.*, t.topic_name, c.course_name
                FROM assignments a 
                JOIN topics t ON a.topic_id = t.topic_id 
                JOIN courses c ON t.course_id = c.course_id 
                JOIN course_trainers ct ON c.course_id = ct.course_id 
                WHERE ct.trainer_id = %s AND a.assignment_id = %s
            """, (current_user.user_id, assignment_id))
            assignment = cursor.fetchone()
            
            if not assignment:
                flash('Access denied to this assignment', 'danger')
                return redirect(url_for('trainer.dashboard'))
            
            # Fetch all submissions for this assignment
            cursor.execute("""
                SELECT asub.*, u.full_name as student_name, b.batch_name
                FROM assignment_submissions asub
                JOIN students s ON asub.student_id = s.student_id
                JOIN users u ON s.user_id = u.user_id
                LEFT JOIN batch_students bs ON s.student_id = bs.student_id AND bs.is_active = TRUE
                LEFT JOIN batches b ON bs.batch_id = b.batch_id
                WHERE asub.assignment_id = %s ORDER BY asub.submitted_at DESC
            """, (assignment_id,))
            submissions = cursor.fetchall()
        except mysql.connector.Error as err:
            flash(f'Error retrieving submissions: {err}', 'danger')
        finally:
            if conn.is_connected(): cursor.close(); conn.close()
            
    return render_template('trainer/submissions.html', assignment=assignment, submissions=submissions)


@trainer_bp.route('/grade_submission/<int:submission_id>', methods=['POST'])
def grade_submission(submission_id):
    data = request.get_json()
    grade = data.get('grade')
    feedback = data.get('feedback', '')

    if not grade:
        return jsonify({'success': False, 'message': 'Grade is a required field.'})

    conn = current_app.get_db_connection()
    try:
        cursor = conn.cursor()
        # Security check: Make sure this trainer owns the assignment
        cursor.execute("""
            SELECT asub.submission_id FROM assignment_submissions asub
            JOIN assignments a ON asub.assignment_id = a.assignment_id
            WHERE a.created_by = %s AND asub.submission_id = %s
        """, (current_user.user_id, submission_id))
        
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Access denied.'})

        cursor.execute("UPDATE assignment_submissions SET grade = %s, feedback = %s, graded_by = %s, graded_at = NOW() WHERE submission_id = %s",
                       (grade, feedback, current_user.user_id, submission_id))
        conn.commit()
        log_activity(current_user.user_id, 'grade', 'assignment_submissions', submission_id, f"Graded submission with a score of {grade}%")
        return jsonify({'success': True, 'message': 'Submission graded successfully'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {err}'})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
# ______________________________
# --- STUDENT MONITORING & REPORTING ROUTES ---

@trainer_bp.route('/students')
def student_overview():
    conn = current_app.get_db_connection()
    courses, batches, students = [], [], []
    selected_course = request.args.get('course_id')
    selected_batch = request.args.get('batch_id')
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT c.course_id, c.course_name FROM courses c JOIN course_trainers ct ON c.course_id = ct.course_id WHERE ct.trainer_id = %s AND c.is_active = TRUE", (current_user.user_id,))
            courses = cursor.fetchall()

            base_query = """
                SELECT 
                    s.student_id, u.full_name, u.email, u.phone, u.is_active, c.course_name, b.batch_name,
                    (SELECT COUNT(*) FROM assignments a_in JOIN topics t_in ON a_in.topic_id = t_in.topic_id WHERE t_in.course_id = c.course_id) as total_assignments,
                    (SELECT COUNT(*) FROM assignment_submissions asub WHERE asub.student_id = s.student_id) as submitted_assignments,
                    (SELECT AVG(grade) FROM assignment_submissions asub WHERE asub.student_id = s.student_id AND grade IS NOT NULL) as avg_grade,
                    (SELECT COUNT(*) FROM attendance att WHERE att.student_id = s.student_id) as total_classes,
                    (SELECT COUNT(*) FROM attendance att WHERE att.student_id = s.student_id AND att.is_present = TRUE) as attended_classes
                FROM students s
                JOIN users u ON s.user_id = u.user_id JOIN courses c ON s.course_id = c.course_id
                JOIN course_trainers ct ON c.course_id = ct.course_id
                LEFT JOIN batch_students bs ON s.student_id = bs.student_id AND bs.is_active = TRUE
                LEFT JOIN batches b ON bs.batch_id = b.batch_id
                WHERE ct.trainer_id = %s
            """
            params = [current_user.user_id]
            if selected_course:
                base_query += " AND c.course_id = %s"
                params.append(selected_course)
            if selected_batch:
                base_query += " AND b.batch_id = %s"
                params.append(selected_batch)
            
            base_query += " GROUP BY s.student_id, u.user_id, c.course_id, b.batch_id"
            cursor.execute(base_query, tuple(params))
            students = cursor.fetchall()

            for student in students:
                student['attendance_percentage'] = round((student.get('attended_classes', 0) / student['total_classes']) * 100, 1) if student.get('total_classes') else 0
        except mysql.connector.Error as err:
            flash(f'Error retrieving students: {err}', 'danger')
        finally:
            if conn.is_connected(): cursor.close(); conn.close()

    return render_template('trainer/student_overview.html', courses=courses, students=students, selected_course=selected_course, selected_batch=selected_batch)




# __________________________________

@trainer_bp.route('/get_student_details/<int:student_id>')
@login_required
def get_student_details(student_id):
    """
    Fetches a comprehensive set of details for a single student via AJAX.
    Accessible only by trainers who are assigned to the student's course.
    """
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'})

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. Security Check and Primary Student/Course/Batch Info
        # This query also fetches the leave limit from the 'batches' table now.
        cursor.execute("""
            SELECT 
                s.student_id, u.full_name, u.email, u.phone, u.is_active,
                c.course_name, b.batch_name, s.course_id,
                b.personal_leave_limit
            FROM students s
            JOIN users u ON s.user_id = u.user_id
            JOIN courses c ON s.course_id = c.course_id
            JOIN course_trainers ct ON c.course_id = ct.course_id
            LEFT JOIN batch_students bs ON s.student_id = bs.student_id AND bs.is_active = TRUE
            LEFT JOIN batches b ON bs.batch_id = b.batch_id
            WHERE ct.trainer_id = %s AND s.student_id = %s
        """, (current_user.user_id, student_id))
        student_data = cursor.fetchone()

        if not student_data:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Access denied or student not found.'})
        
        course_id = student_data['course_id']

        # 2. Performance Statistics (Attendance, Assignments, Leaves)
        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM attendance att WHERE att.student_id = s.student_id) as total_classes,
                (SELECT COUNT(*) FROM attendance att WHERE att.student_id = s.student_id AND att.is_present = TRUE) as attended_classes,
                (SELECT COUNT(*) FROM assignments a_in 
                 JOIN batch_students bs_in ON a_in.batch_id = bs_in.batch_id 
                 WHERE bs_in.student_id = s.student_id AND a_in.is_active = TRUE) as total_assignments,
                (SELECT COUNT(*) FROM assignment_submissions asub WHERE asub.student_id = s.student_id) as submitted_assignments,
                (SELECT AVG(grade) FROM assignment_submissions asub WHERE asub.student_id = s.student_id AND grade IS NOT NULL) as avg_grade,
                (SELECT COUNT(*) FROM leave_applications la WHERE la.student_id = s.student_id AND la.status = 'approved') as approved_leaves
            FROM students s
            WHERE s.student_id = %s
        """, (student_id,))
        performance_stats = cursor.fetchone()
        
        # Merge stats into the main student_data dictionary
        if performance_stats:
            student_data.update(performance_stats)
            if student_data.get('total_classes', 0) > 0:
                student_data['attendance_percentage'] = round((student_data.get('attended_classes', 0) / student_data['total_classes']) * 100, 1)
            else:
                student_data['attendance_percentage'] = 0

        # 3. Get detailed assignment history for the student's batch
        cursor.execute("""
            SELECT 
                a.title, asub.submitted_at, asub.grade, asub.feedback,
                CASE 
                    WHEN asub.grade IS NOT NULL THEN 'Graded'
                    WHEN asub.submitted_at IS NOT NULL THEN 'Submitted'
                    ELSE 'Pending' 
                END as status
            FROM assignments a
            JOIN batch_students bs ON a.batch_id = bs.batch_id
            LEFT JOIN assignment_submissions asub ON a.assignment_id = asub.assignment_id AND asub.student_id = bs.student_id
            WHERE bs.student_id = %s
            ORDER BY a.due_date
        """, (student_id,))
        assignments = cursor.fetchall()

        # 4. Get recent attendance records
        cursor.execute("""
            SELECT attendance_date, is_present 
            FROM attendance 
            WHERE student_id = %s 
            ORDER BY attendance_date DESC 
            LIMIT 30
        """, (student_id,))
        attendance = cursor.fetchall()
        # Convert date objects to strings for JSON serialization
        for record in attendance:
            record['attendance_date'] = record['attendance_date'].strftime('%Y-%m-%d')

        # 5. Get recent leave history
        cursor.execute("""
            SELECT start_date, end_date, reason, status, admin_comments 
            FROM leave_applications 
            WHERE student_id = %s 
            ORDER BY applied_at DESC 
            LIMIT 10
        """, (student_id,))
        leaves = cursor.fetchall()
        # Convert date objects to strings for JSON serialization
        for leave in leaves:
            leave['start_date'] = leave['start_date'].strftime('%Y-%m-%d')
            leave['end_date'] = leave['end_date'].strftime('%Y-%m-%d')

        return jsonify({
            'success': True, 
            'student': student_data,
            'assignments': assignments,
            'attendance': attendance,
            'leaves': leaves
        })

    except mysql.connector.Error as err:
        print(f"Error getting student details: {err}")
        return jsonify({'success': False, 'message': f'A database error occurred: {err}'})
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()





# ___________________________________-



@trainer_bp.route('/export_students')
def export_students():
    course_id = request.args.get('course_id')
    batch_id = request.args.get('batch_id')
    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error', 'danger')
        return redirect(url_for('trainer.student_overview'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Base query
        query = """
            SELECT u.full_name, u.email, u.phone, u.is_active, c.course_name, b.batch_name,
                (SELECT COUNT(*) FROM assignments a_in JOIN topics t_in ON a_in.topic_id = t_in.topic_id WHERE t_in.course_id = c.course_id) as total_assignments,
                (SELECT COUNT(*) FROM assignment_submissions asub WHERE asub.student_id = s.student_id) as submitted_assignments,
                (SELECT AVG(grade) FROM assignment_submissions asub WHERE asub.student_id = s.student_id AND grade IS NOT NULL) as avg_grade
            FROM students s
            JOIN users u ON s.user_id = u.user_id
            JOIN courses c ON s.course_id = c.course_id
            JOIN course_trainers ct ON c.course_id = ct.course_id
            LEFT JOIN batch_students bs ON s.student_id = bs.student_id AND bs.is_active = TRUE
            LEFT JOIN batches b ON bs.batch_id = b.batch_id
            WHERE ct.trainer_id = %s
        """
        params = [current_user.user_id]
        if course_id:
            query += " AND s.course_id = %s"
            params.append(course_id)
        if batch_id:
            query += " AND b.batch_id = %s"
            params.append(batch_id)
        
        query += " GROUP BY s.student_id, u.user_id, c.course_id, b.batch_id ORDER BY u.full_name"
        cursor.execute(query, tuple(params))
        students = cursor.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        header = ['Student Name', 'Email', 'Phone', 'Status', 'Course', 'Batch', 'Total Assignments', 'Submitted', 'Average Grade']
        writer.writerow(header)

        for student in students:
            row = [
                student['full_name'], student['email'], student['phone'],
                'Active' if student['is_active'] else 'Inactive',
                student['course_name'], student['batch_name'] or 'N/A',
                student['total_assignments'], student['submitted_assignments'],
                f"{student['avg_grade']:.2f}%" if student['avg_grade'] is not None else 'N/A'
            ]
            writer.writerow(row)
        
        response = current_app.response_class(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=student_overview.csv'}
        )
        log_activity(current_user.user_id, 'export', 'students', 0, "Exported student overview")
        return response

    except mysql.connector.Error as err:
        flash(f'Error exporting data: {err}', 'danger')
        return redirect(url_for('trainer.student_overview'))
    finally:
        if conn.is_connected(): cursor.close(); conn.close()



@trainer_bp.route('/update_assignment/<int:assignment_id>', methods=['POST'])
@login_required
def update_assignment(assignment_id):
    """Handles updating an existing assignment."""
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'})

    try:
        cursor = conn.cursor(dictionary=True)
        # Security Check: Ensure trainer owns this assignment
        cursor.execute("SELECT created_by, file_path FROM assignments WHERE assignment_id = %s", (assignment_id,))
        assignment = cursor.fetchone()
        if not assignment or assignment['created_by'] != current_user.user_id:
            return jsonify({'success': False, 'message': 'Access denied.'})

        # Update text fields
        cursor.execute("""
            UPDATE assignments SET title=%s, description=%s, topic_id=%s, due_date=%s, 
            assignment_type=%s, max_points=%s, is_active=%s 
            WHERE assignment_id=%s
        """, (
            request.form.get('title'), request.form.get('description'), request.form.get('topic_id'),
            request.form.get('due_date'), request.form.get('assignment_type'), request.form.get('max_points'),
            '1' if request.form.get('is_active') == 'true' else '0',
            assignment_id
        ))

        # Handle optional file update
        if 'assignment_file' in request.files:
            file = request.files['assignment_file']
            if file.filename != '':
                # (Optional) Delete old file before saving new one
                if assignment['file_path']:
                    old_file_full_path = os.path.join(current_app.root_path, 'static', assignment['file_path'])
                    if os.path.exists(old_file_full_path):
                        os.remove(old_file_full_path)

                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'assignments')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"assignment_{assignment_id}_{file.filename}"
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                relative_path = os.path.join('uploads', 'assignments', filename).replace("\\", "/")
                cursor.execute("UPDATE assignments SET file_path = %s WHERE assignment_id = %s", (relative_path, assignment_id))

        conn.commit()
        log_activity(current_user.user_id, 'update', 'assignments', assignment_id, f"Updated assignment: {request.form.get('title')}")
        return jsonify({'success': True, 'message': 'Assignment updated successfully!'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database Error: {err}'})
    finally:
        if conn and conn.is_connected(): cursor.close(); conn.close()


@trainer_bp.route('/delete_assignment/<int:assignment_id>', methods=['POST'])
@login_required
def delete_assignment(assignment_id):
    """Handles deleting an assignment."""
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error.'})
        
    try:
        cursor = conn.cursor(dictionary=True)
        # Security Check: Ensure trainer owns this assignment
        cursor.execute("SELECT created_by, file_path, title FROM assignments WHERE assignment_id = %s", (assignment_id,))
        assignment = cursor.fetchone()
        if not assignment or assignment['created_by'] != current_user.user_id:
            return jsonify({'success': False, 'message': 'Access denied.'})
        
        # (Optional) Delete the associated file from the server
        if assignment['file_path']:
            file_full_path = os.path.join(current_app.root_path, 'static', assignment['file_path'])
            if os.path.exists(file_full_path):
                os.remove(file_full_path)

        # Note: Submissions will be deleted automatically by the CASCADE constraint in your DB
        cursor.execute("DELETE FROM assignments WHERE assignment_id = %s", (assignment_id,))
        conn.commit()

        log_activity(current_user.user_id, 'delete', 'assignments', assignment_id, f"Deleted assignment: {assignment['title']}")
        return jsonify({'success': True, 'message': 'Assignment deleted successfully.'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database Error: {err}'})
    finally:
        if conn and conn.is_connected(): cursor.close(); conn.close()


























