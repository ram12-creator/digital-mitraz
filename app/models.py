from flask_login import UserMixin
import mysql.connector
from flask import current_app
import bcrypt
from datetime import datetime, timedelta

from app import login_manager

class User(UserMixin):
    def __init__(self, user_id, email, password_hash, full_name, phone, role, is_active, 
                 created_by=None, first_name=None, last_name=None, qualifications=None, profile_picture=None, gender=None,
                 # Student-specific attributes
                 student_id=None, course_id=None, enrollment_date=None, course_name=None,
                 batch_id=None, batch_name=None):
        
        self.user_id = user_id
        self.email = email
        self.password_hash = password_hash
        self.full_name = full_name
        self.phone = phone
        self.role = role
        self._is_active = is_active
        self.created_by = created_by
        self.first_name = first_name
        self.last_name = last_name
        self.qualifications = qualifications
        self.profile_picture = profile_picture
        self.gender = gender
        
        # Student-specific attributes
        self.student_id = student_id
        self.course_id = course_id
        self.enrollment_date = enrollment_date
        self.course_name = course_name
        self.batch_id = batch_id
        self.batch_name = batch_name

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = value

    def get_id(self):
        return str(self.user_id)
    
    @staticmethod
    def get(user_id):
        conn = current_app.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            # UPDATED QUERY: Joins batches to get course info
            cursor.execute("""
                SELECT 
                    u.*, 
                    s.student_id, 
                    b.course_id,         -- Get course_id from batches table
                    s.created_at as enrollment_date, 
                    c.course_name, 
                    b.batch_name, 
                    b.batch_id
                FROM users u 
                LEFT JOIN students s ON u.user_id = s.user_id 
                LEFT JOIN batches b ON s.batch_id = b.batch_id 
                LEFT JOIN courses c ON b.course_id = c.course_id 
                WHERE u.user_id = %s
            """, (user_id,))
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user_data:
                return User(
                    user_id=user_data['user_id'], email=user_data['email'],
                    password_hash=user_data['password_hash'], full_name=user_data['full_name'],
                    phone=user_data['phone'], role=user_data['role'], is_active=user_data['is_active'],
                    created_by=user_data.get('created_by'), first_name=user_data.get('first_name'),
                    last_name=user_data.get('last_name'), qualifications=user_data.get('qualifications'),
                    profile_picture=user_data.get('profile_picture'),
                    gender=user_data.get('gender'),
                    # Student specific data
                    student_id=user_data.get('student_id'), 
                    course_id=user_data.get('course_id'),
                    enrollment_date=user_data.get('enrollment_date'), 
                    course_name=user_data.get('course_name'),
                    batch_id=user_data.get('batch_id'), 
                    batch_name=user_data.get('batch_name')
                )
        return None
    
    @staticmethod
    def get_by_email(email):
        conn = current_app.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            # UPDATED QUERY: Joins batches to get course info
            cursor.execute("""
                SELECT 
                    u.*, 
                    s.student_id, 
                    b.course_id,         -- Get course_id from batches table
                    s.created_at as enrollment_date, 
                    c.course_name, 
                    b.batch_name, 
                    b.batch_id
                FROM users u 
                LEFT JOIN students s ON u.user_id = s.user_id 
                LEFT JOIN batches b ON s.batch_id = b.batch_id 
                LEFT JOIN courses c ON b.course_id = c.course_id 
                WHERE u.email = %s
            """, (email,))
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user_data:
                return User(
                    user_id=user_data['user_id'], email=user_data['email'],
                    password_hash=user_data['password_hash'], full_name=user_data['full_name'],
                    phone=user_data['phone'], role=user_data['role'], is_active=user_data['is_active'],
                    created_by=user_data.get('created_by'), first_name=user_data.get('first_name'),
                    last_name=user_data.get('last_name'), qualifications=user_data.get('qualifications'),
                    profile_picture=user_data.get('profile_picture'),
                    gender=user_data.get('gender'),
                    # Student specific data
                    student_id=user_data.get('student_id'), 
                    course_id=user_data.get('course_id'),
                    enrollment_date=user_data.get('enrollment_date'), 
                    course_name=user_data.get('course_name'),
                    batch_id=user_data.get('batch_id'), 
                    batch_name=user_data.get('batch_name')
                )
        return None
    
    @staticmethod
    def validate_login(email, password):
        user = User.get_by_email(email)
        if user and user.is_active and user.check_password(password):
            return user
        return None
    
    @staticmethod
    def create_user(email, password_hash, full_name, phone, role, created_by=None, 
                   first_name=None, last_name=None, qualifications=None, profile_picture=None, gender=None):
        conn = current_app.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (email, password_hash, full_name, phone, role, created_by, first_name, last_name, qualifications, profile_picture, gender) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (email, password_hash, full_name, phone, role, created_by, first_name, last_name, qualifications, profile_picture, gender)
                )
                user_id = cursor.lastrowid
                conn.commit()
                return user_id
            except mysql.connector.Error as err:
                print(f"Error creating user: {err}")
                conn.rollback()
                return None
            finally:
                if conn.is_connected():
                    cursor.close()
                    conn.close()
        return None
    
    def check_password(self, password):
        if self.password_hash:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        return False
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def update_password(user_id, new_password_hash):
        conn = current_app.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", (new_password_hash, user_id))
                conn.commit()
                return True
            except mysql.connector.Error as err:
                print(f"Error updating password: {err}")
                conn.rollback()
                return False
            finally:
                if conn.is_connected():
                    cursor.close()
                    conn.close()
        return False

    def get_leave_balance(self, batch_id, leave_type_id):
        """
        Fetches remaining leave days.
        """
        conn = current_app.get_db_connection()
        if not conn: return 0, 0

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT type_name, has_limit, default_limit_days FROM leave_types WHERE leave_type_id = %s", (leave_type_id,))
            leave_type = cursor.fetchone()
            
            if not leave_type: return 0, 0

            has_limit = leave_type['has_limit']
            # With new DB, limits are primarily on the batch table or global defaults
            # Simplified logic for new schema:
            max_days = leave_type['default_limit_days'] if has_limit and leave_type['default_limit_days'] is not None else float('inf')
            
            # Use batch specific override if available (need to query batches table if implemented)
            # For now using default

            cursor.execute("""
                SELECT SUM(days_requested) as used_days
                FROM leave_applications
                WHERE student_id = %s AND batch_id = %s AND leave_type_id = %s AND status = 'approved'
            """, (self.student_id, batch_id, leave_type_id)) # Note: using self.student_id
            
            used_data = cursor.fetchone()
            used_days = used_data['used_days'] if used_data and used_data['used_days'] else 0

            remaining_days = 'Unlimited'
            if has_limit and max_days != float('inf'):
                remaining_days = max(0, int(max_days) - int(used_days))
            
            return remaining_days, max_days

        except mysql.connector.Error as err:
            print(f"Error getting leave balance: {err}")
            return 0, 0
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    def get_all_leave_balances_for_batch(self, batch_id):
        balances = {}
        conn = current_app.get_db_connection()
        if not (conn and self.student_id and batch_id): return balances

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT leave_type_id, type_name, has_limit, default_limit_days FROM leave_types ORDER BY type_name")
            leave_types = cursor.fetchall()
            
            # Fetch batch specific limits if applicable (columns like personal_leave_limit in batches table)
            cursor.execute("SELECT * FROM batches WHERE batch_id = %s", (batch_id,))
            batch_data = cursor.fetchone()

            for lt in leave_types:
                type_name = lt['type_name']
                max_days = lt['default_limit_days'] if lt['has_limit'] else float('inf')
                
                # Check for batch override (naming convention assumption: type_name_lower + '_leave_limit')
                limit_col = f"{type_name.lower()}_leave_limit"
                if batch_data and limit_col in batch_data and batch_data[limit_col] is not None:
                    max_days = batch_data[limit_col]

                cursor.execute("""
                    SELECT COALESCE(SUM(days_requested), 0) as used_days
                    FROM leave_applications
                    WHERE student_id = %s AND batch_id = %s AND leave_type_id = %s AND status = 'approved'
                """, (self.student_id, batch_id, lt['leave_type_id']))
                
                used_days = cursor.fetchone()['used_days']
                
                remaining = 'Unlimited'
                if max_days != float('inf'):
                    remaining = max(0, int(max_days) - int(used_days))
                
                balances[type_name] = {'remaining': remaining, 'total': max_days if max_days != float('inf') else 'Unlimited'}
            
        except mysql.connector.Error as err:
            print(f"Error getting all leave balances: {err}")
        finally:
            if conn.is_connected(): cursor.close(); conn.close()
        
        return balances

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)