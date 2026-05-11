
# # _________________________________________________________--

# from app.extensions import celery
# from flask import current_app
# import mysql.connector
# import os
# import subprocess
# import openpyxl
# import pandas as pd
# from sqlalchemy import create_engine, text
# from bs4 import BeautifulSoup
# import cssutils
# import zipfile

# # ===============================================================
# # EVALUATION ENGINES
# # ===============================================================

# def _evaluate_python(submission_file_path, test_case_file_path):
#     """Evaluates a Python submission."""
#     try:
#         command = ['python', test_case_file_path, submission_file_path]
#         result = subprocess.run(command, capture_output=True, text=True, timeout=30)
#         output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
#         if result.returncode == 0 and "OK" in result.stdout:
#             grade = 100
#             feedback = "All test cases passed successfully. Excellent work!"
#         else:
#             grade = 25
#             feedback = "Some test cases failed. Please review the output for errors."
#         return {'grade': grade, 'feedback': feedback, 'output': output}
#     except subprocess.TimeoutExpired:
#         return {'grade': 0, 'feedback': "Evaluation failed: Code took too long to execute.", 'output': 'Timeout Error'}
#     except Exception as e:
#         return {'grade': 0, 'feedback': "An error occurred during evaluation.", 'output': str(e)}

# def _evaluate_sql(submission_file_path, test_case_file_path):
#     """Compares the result set of a student's SQL query against a solution query."""
#     db_config = current_app.config['DB_CONFIG']
#     connection_string = f"mysql+mysqlconnector://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
#     engine = create_engine(connection_string)
#     try:
#         with open(submission_file_path, 'r') as f: student_query = f.read()
#         with open(test_case_file_path, 'r') as f: solution_query = f.read()
#         with engine.connect() as conn:
#             student_df = pd.read_sql(text(student_query), conn)
#             solution_df = pd.read_sql(text(solution_query), conn)
#         if student_df.equals(solution_df):
#             grade, feedback = 100, "Correct! The query produced the exact expected result."
#         elif list(student_df.columns) == list(solution_df.columns):
#             grade, feedback = 50, "The columns are correct, but the data is different. Check your WHERE clauses or JOINs."
#         else:
#             grade, feedback = 10, "The query ran, but the columns in the result are incorrect."
#         output = f"--- STUDENT RESULT ---\n{student_df.to_string()}\n\n--- EXPECTED RESULT ---\n{solution_df.to_string()}"
#         return {'grade': grade, 'feedback': feedback, 'output': output}
#     except Exception as e:
#         return {'grade': 0, 'feedback': "Your SQL query failed to execute.", 'output': str(e)}

# def _evaluate_excel(submission_file_path, test_case_file_path):
#     """Compares values in a student's Excel file against a solution."""
#     try:
#         student_wb = openpyxl.load_workbook(submission_file_path)
#         solution_wb = openpyxl.load_workbook(test_case_file_path)
#         student_sheet = student_wb.active
#         solution_sheet = solution_wb.active
#         tests = [{'cell': 'B5', 'type': 'value', 'weight': 100}] # Simple example
#         grade = 0
#         feedback_lines = []
#         for test in tests:
#             cell, student_val, solution_val = test['cell'], student_sheet[cell].value, solution_sheet[cell].value
#             is_correct = (student_val == solution_val)
#             feedback_lines.append(f"Cell {cell} Value Check: {'PASS' if is_correct else 'FAIL'}. Expected '{solution_val}', got '{student_val}'.")
#             if is_correct: grade += test['weight']
#         feedback = "\n".join(feedback_lines)
#         return {'grade': grade, 'feedback': feedback, 'output': feedback}
#     except Exception as e:
#         return {'grade': 0, 'feedback': "Could not process the Excel file.", 'output': str(e)}

# def _evaluate_web(submission_file_path, test_case_file_path):
#     """Checks for specific elements in HTML/CSS files from a ZIP archive."""
#     try:
#         extract_dir = os.path.join(os.path.dirname(submission_file_path), 'unzipped_web')
#         with zipfile.ZipFile(submission_file_path, 'r') as zip_ref:
#             zip_ref.extractall(extract_dir)
#         html_file = next((os.path.join(extract_dir, f) for f in os.listdir(extract_dir) if f.endswith('.html')), None)
#         if not html_file: return {'grade': 0, 'feedback': "No HTML file found in the .zip archive.", 'output': ''}
#         with open(html_file, 'r', encoding='utf-8') as f: soup = BeautifulSoup(f, 'html.parser')
#         grade, feedback_lines = 0, []
#         if soup.title and soup.title.string:
#             grade += 50; feedback_lines.append("PASS: Page has a valid <title> tag.")
#         else:
#             feedback_lines.append("FAIL: Page is missing a <title> tag.")
#         if soup.find('h1'):
#             grade += 50; feedback_lines.append("PASS: An <h1> heading was found.")
#         else:
#             feedback_lines.append("FAIL: No <h1> heading was found.")
#         feedback = "\n".join(feedback_lines)
#         return {'grade': grade, 'feedback': feedback, 'output': feedback}
#     except Exception as e:
#         return {'grade': 0, 'feedback': "An error occurred while evaluating the web files.", 'output': str(e)}

# # ===============================================================
# # MAIN CELERY TASK
# # ===============================================================
# @celery.task(name='app.tasks.evaluate_submission')
# def evaluate_submission(submission_id):
#     db_config = current_app.config['DB_CONFIG']
#     conn = mysql.connector.connect(**db_config)
#     cursor = conn.cursor(dictionary=True)

#     try:
#         cursor.execute("""
#             SELECT 
#                 asub.file_path as submission_file,
#                 a.evaluation_type,
#                 a.test_case_file_path as test_file
#             FROM assignment_submissions asub
#             JOIN assignments a ON asub.assignment_id = a.assignment_id
#             WHERE asub.submission_id = %s
#         """, (submission_id,))
#         task_data = cursor.fetchone()

#         if not task_data or not task_data['evaluation_type'] or task_data['evaluation_type'] == 'none':
#             return "Not an auto-graded assignment."
        
#         is_web_eval = task_data['evaluation_type'] == 'web'
#         if not is_web_eval and not task_data['test_file']:
#             raise ValueError("Test case file is missing for this evaluation type.")

#         cursor.execute("UPDATE assignment_submissions SET evaluation_status = 'processing' WHERE submission_id = %s", (submission_id,))
#         conn.commit()

#         base_path = current_app.root_path
#         submission_path = os.path.join(base_path, 'static', task_data['submission_file'])
#         test_case_path = os.path.join(base_path, 'static', task_data['test_file']) if task_data['test_file'] else None
        
#         result = {}
#         evaluation_type = task_data['evaluation_type']

#         if evaluation_type == 'python':
#             result = _evaluate_python(submission_path, test_case_path)
#         elif evaluation_type == 'sql':
#             result = _evaluate_sql(submission_path, test_case_path)
#         elif evaluation_type == 'excel':
#             result = _evaluate_excel(submission_path, test_case_path)
#         elif evaluation_type == 'web':
#             result = _evaluate_web(submission_path, test_case_path)
#         else:
#             raise TypeError("Unsupported evaluation type.")

#         cursor.execute("""
#             UPDATE assignment_submissions 
#             SET auto_grade = %s, auto_feedback = %s, evaluation_output = %s, evaluation_status = 'completed'
#             WHERE submission_id = %s
#         """, (result.get('grade'), result.get('feedback'), result.get('output'), submission_id))
#         conn.commit()

#     except Exception as e:
#         # Ensure conn is defined for rollback
#         if 'conn' in locals() and conn.is_connected():
#             conn.rollback()
#             cursor.execute("UPDATE assignment_submissions SET evaluation_status = 'error', evaluation_output = %s WHERE submission_id = %s", (str(e), submission_id))
#             conn.commit()
#         print(f"CELERY TASK FAILED for submission_id {submission_id}: {e}")
#     finally:
#         if 'conn' in locals() and conn.is_connected():
#             cursor.close()
#             conn.close()



from app.extensions import celery
from flask import current_app
import mysql.connector
import os
import subprocess
import openpyxl
import pandas as pd
from sqlalchemy import create_engine, text
from bs4 import BeautifulSoup
import zipfile
import sys # Import sys to get the current python interpreter path

# ===============================================================
# EVALUATION ENGINES
# ===============================================================

def _evaluate_python(submission_file_path, test_case_file_path):
    """Evaluates a Python submission."""
    try:
        # FIX: Use sys.executable to ensure we use the SAME python environment (venv)
        # that Celery is using, rather than the global 'python' command.
        python_exe = sys.executable 
        
        command = [python_exe, test_case_file_path, submission_file_path]
        
        # Run the process
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            timeout=30,
            cwd=os.path.dirname(test_case_file_path) # Run in the test case directory
        )
        
        output = f"EXIT CODE: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        
        # Grading Logic
        if result.returncode == 0:
            # Flexible checking: Look for "OK" OR "passed" (case insensitive)
            if "OK" in result.stdout or "passed" in result.stdout.lower():
                grade = 100
                feedback = "Automated Tests Passed."
            else:
                grade = 50
                feedback = "Code ran successfully, but did not output 'OK'. Check test case requirements."
        else:
            grade = 0
            feedback = "Runtime Error. Code failed to execute."

        return {'grade': grade, 'feedback': feedback, 'output': output}

    except subprocess.TimeoutExpired:
        return {'grade': 0, 'feedback': "Timeout: Code took too long to execute (>30s).", 'output': 'Timeout Error'}
    except Exception as e:
        return {'grade': 0, 'feedback': "System Error during execution.", 'output': str(e)}

# ... (Keep _evaluate_sql, _evaluate_excel, _evaluate_web exactly as they were) ...
# [Paste your existing SQL, Excel, Web functions here]

def _evaluate_sql(submission_file_path, test_case_file_path):
    """Compares the result set of a student's SQL query against a solution query."""
    db_config = current_app.config['DB_CONFIG']
    # Use pymysql or mysql-connector for sqlalchemy
    connection_string = f"mysql+mysqlconnector://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    engine = create_engine(connection_string)
    try:
        with open(submission_file_path, 'r') as f: student_query = f.read()
        with open(test_case_file_path, 'r') as f: solution_query = f.read()
        with engine.connect() as conn:
            student_df = pd.read_sql(text(student_query), conn)
            solution_df = pd.read_sql(text(solution_query), conn)
        if student_df.equals(solution_df):
            grade, feedback = 100, "Correct! The query produced the exact expected result."
        elif list(student_df.columns) == list(solution_df.columns):
            grade, feedback = 50, "The columns are correct, but the data is different. Check your WHERE clauses or JOINs."
        else:
            grade, feedback = 10, "The query ran, but the columns in the result are incorrect."
        output = f"--- STUDENT RESULT ---\n{student_df.to_string()}\n\n--- EXPECTED RESULT ---\n{solution_df.to_string()}"
        return {'grade': grade, 'feedback': feedback, 'output': output}
    except Exception as e:
        return {'grade': 0, 'feedback': "Your SQL query failed to execute.", 'output': str(e)}

def _evaluate_excel(submission_file_path, test_case_file_path):
    """Compares values in a student's Excel file against a solution."""
    try:
        student_wb = openpyxl.load_workbook(submission_file_path)
        solution_wb = openpyxl.load_workbook(test_case_file_path)
        student_sheet = student_wb.active
        solution_sheet = solution_wb.active
        tests = [{'cell': 'B5', 'type': 'value', 'weight': 100}] # Simple example
        grade = 0
        feedback_lines = []
        for test in tests:
            cell, student_val, solution_val = test['cell'], student_sheet[cell].value, solution_sheet[cell].value
            is_correct = (student_val == solution_val)
            feedback_lines.append(f"Cell {cell} Value Check: {'PASS' if is_correct else 'FAIL'}. Expected '{solution_val}', got '{student_val}'.")
            if is_correct: grade += test['weight']
        feedback = "\n".join(feedback_lines)
        return {'grade': grade, 'feedback': feedback, 'output': feedback}
    except Exception as e:
        return {'grade': 0, 'feedback': "Could not process the Excel file.", 'output': str(e)}

def _evaluate_web(submission_file_path, test_case_file_path):
    """Checks for specific elements in HTML/CSS files from a ZIP archive."""
    try:
        extract_dir = os.path.join(os.path.dirname(submission_file_path), 'unzipped_web')
        with zipfile.ZipFile(submission_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        html_file = next((os.path.join(extract_dir, f) for f in os.listdir(extract_dir) if f.endswith('.html')), None)
        if not html_file: return {'grade': 0, 'feedback': "No HTML file found in the .zip archive.", 'output': ''}
        with open(html_file, 'r', encoding='utf-8') as f: soup = BeautifulSoup(f, 'html.parser')
        grade, feedback_lines = 0, []
        if soup.title and soup.title.string:
            grade += 50; feedback_lines.append("PASS: Page has a valid <title> tag.")
        else:
            feedback_lines.append("FAIL: Page is missing a <title> tag.")
        if soup.find('h1'):
            grade += 50; feedback_lines.append("PASS: An <h1> heading was found.")
        else:
            feedback_lines.append("FAIL: No <h1> heading was found.")
        feedback = "\n".join(feedback_lines)
        return {'grade': grade, 'feedback': feedback, 'output': feedback}
    except Exception as e:
        return {'grade': 0, 'feedback': "An error occurred while evaluating the web files.", 'output': str(e)}


# ===============================================================
# MAIN CELERY TASK
# ===============================================================
@celery.task(name='app.tasks.evaluate_submission')
def evaluate_submission(submission_id):
    print(f"--- STARTING EVALUATION FOR SUBMISSION ID: {submission_id} ---") # Log start
    
    db_config = current_app.config['DB_CONFIG']
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                asub.file_path as submission_file,
                a.evaluation_type,
                a.test_case_file_path as test_file
            FROM assignment_submissions asub
            JOIN assignments a ON asub.assignment_id = a.assignment_id
            WHERE asub.submission_id = %s
        """, (submission_id,))
        task_data = cursor.fetchone()

        if not task_data:
            print(f"Error: Submission {submission_id} not found in DB.")
            return "Submission not found"

        print(f"Evaluation Type: {task_data['evaluation_type']}")
        
        if not task_data['evaluation_type'] or task_data['evaluation_type'] == 'none':
            print("Skipping: Not an auto-graded assignment.")
            return "Not an auto-graded assignment."
        
        is_web_eval = task_data['evaluation_type'] == 'web'
        if not is_web_eval and not task_data['test_file']:
            raise ValueError("Test case file is missing for this evaluation type.")

        cursor.execute("UPDATE assignment_submissions SET evaluation_status = 'processing' WHERE submission_id = %s", (submission_id,))
        conn.commit()

        base_path = current_app.root_path
        
        # SAFE PATH JOINING FOR WINDOWS
        # Normalize the DB paths to use correct OS separators
        sub_rel = task_data['submission_file'].replace('/', os.sep).replace('\\', os.sep)
        submission_path = os.path.join(base_path, 'static', sub_rel)
        
        test_case_path = None
        if task_data['test_file']:
            test_rel = task_data['test_file'].replace('/', os.sep).replace('\\', os.sep)
            test_case_path = os.path.join(base_path, 'static', test_rel)

        print(f"Evaluating file: {submission_path}")
        print(f"Using Test Case: {test_case_path}")

        if not os.path.exists(submission_path):
            raise FileNotFoundError(f"Submission file not found at: {submission_path}")
        
        result = {}
        evaluation_type = task_data['evaluation_type']

        if evaluation_type == 'python':
            result = _evaluate_python(submission_path, test_case_path)
        elif evaluation_type == 'sql':
            result = _evaluate_sql(submission_path, test_case_path)
        elif evaluation_type == 'excel':
            result = _evaluate_excel(submission_path, test_case_path)
        elif evaluation_type == 'web':
            result = _evaluate_web(submission_path, test_case_path)
        else:
            raise TypeError("Unsupported evaluation type.")

        print(f"Evaluation Result: Grade={result.get('grade')}")

        cursor.execute("""
            UPDATE assignment_submissions 
            SET auto_grade = %s, auto_feedback = %s, evaluation_output = %s, evaluation_status = 'completed'
            WHERE submission_id = %s
        """, (result.get('grade'), result.get('feedback'), result.get('output'), submission_id))
        conn.commit()
        return f"Success: Grade {result.get('grade')}"

    except Exception as e:
        print(f"CELERY TASK FAILED for submission_id {submission_id}: {e}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            cursor.execute("UPDATE assignment_submissions SET evaluation_status = 'error', evaluation_output = %s WHERE submission_id = %s", (str(e), submission_id))
            conn.commit()
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()