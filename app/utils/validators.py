
# ____________________________________________________________________________

import re
from datetime import datetime, timedelta
from flask import current_app
import mysql.connector

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    digits = re.sub(r'\D', '', phone)
    return 10 <= len(digits) <= 15

def validate_password(password):
    if len(password) < 8: return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password): return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password): return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password): return False, "Password must contain at least one number"
    return True, "Password is valid"

def validate_date_range(start_date_str, end_date_str):
    try:
        start = datetime.strptime(start_date_str, '%Y-%m-%d')
        end = datetime.strptime(end_date_str, '%Y-%m-%d')
        return start <= end
    except (ValueError, TypeError):
        return False

def validate_course_dates(start_date_str, end_date_str, duration_weeks):
    try:
        start = datetime.strptime(start_date_str, '%Y-%m-%d')
        end = datetime.strptime(end_date_str, '%Y-%m-%d')
        expected_end = start + timedelta(weeks=duration_weeks)
        min_end = expected_end - timedelta(weeks=2)
        max_end = expected_end + timedelta(weeks=2)
        return min_end <= end <= max_end
    except (ValueError, TypeError):
        return False

def validate_csv_headers(headers, expected_headers):
    return set(headers) == set(expected_headers)

def validate_leave_dates(start_date_str, end_date_str, leave_type_id, student_id, batch_id):
    """
    Validates leave application with the new '2-Day Notice' rule for Personal Leave.
    """
    conn = current_app.get_db_connection()
    if not conn: return False, "Database connection error"
    
    try:
        start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        today = datetime.now().date()
        
        # 1. Basic Validation
        if end < start:
            return False, "End date must be after start date."
        if start < today:
            return False, "You cannot apply for leave in the past."

        cursor = conn.cursor(dictionary=True)
        
        # 2. Get Leave Type Name to check for 'Personal'
        cursor.execute("SELECT type_name, has_limit, default_limit_days FROM leave_types WHERE leave_type_id = %s", (leave_type_id,))
        leave_type = cursor.fetchone()
        
        if not leave_type:
            return False, "Invalid leave type."

        # ============================================================
        # NEW RULE: 2-Day Prior Notice for Personal Leave
        # ============================================================
        if leave_type['type_name'] == 'Personal':
            # Calculate difference in days
            days_notice = (start - today).days
            if days_notice < 2:
                return False, f"Personal Leave requires at least 2 days prior notice. Earliest you can apply for is {(today + timedelta(days=2)).strftime('%d-%b-%Y')}."

        # 3. Existing Logic: Check Leave Balance
        max_days = float('inf')
        if leave_type['has_limit']:
            # Check student allowance overrides
            cursor.execute("""
                SELECT allowed_days FROM student_leave_allowances
                WHERE student_id = %s AND batch_id = %s AND leave_type_id = %s
            """, (student_id, batch_id, leave_type_id))
            allowance = cursor.fetchone()
            
            # Use batch/global limit if no override
            if allowance:
                max_days = allowance['allowed_days']
            else:
                # Fallback to batch limit if configured, else default
                cursor.execute(f"SELECT {leave_type['type_name'].lower()}_leave_limit FROM batches WHERE batch_id = %s", (batch_id,))
                batch_limit = cursor.fetchone()
                # Use batch specific limit column if it exists, else default
                if batch_limit and list(batch_limit.values())[0] is not None:
                     max_days = list(batch_limit.values())[0]
                else:
                     max_days = leave_type['default_limit_days'] or 0

        # Calculate requested days (excluding weekends)
        leave_days = 0
        current = start
        while current <= end:
            if current.weekday() < 5:  # Monday to Friday
                leave_days += 1
            current += timedelta(days=1)
            
        if leave_days == 0:
             return False, "You selected only weekends. No leave needed."

        # Check Usage
        cursor.execute("""
            SELECT SUM(days_requested) as used_days
            FROM leave_applications
            WHERE student_id = %s AND batch_id = %s AND leave_type_id = %s AND status = 'approved'
        """, (student_id, batch_id, leave_type_id))
        used = cursor.fetchone()['used_days'] or 0

        if (used + leave_days) > max_days:
            return False, f"Insufficient balance. You have {int(max_days - used)} days remaining for {leave_type['type_name']}."
        
        return True, "Valid"
        
    except ValueError:
        return False, "Invalid date format."
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()