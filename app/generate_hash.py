# update_admin_password.py
import mysql.connector
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

# --- Configuration ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}
TARGET_EMAIL = 'superadmin@mitraz.com' # The email of the user to update
NEW_PASSWORD = 'admin123'             # The new password you want to set

def update_password_in_db():
    try:
        # Generate a fresh, valid bcrypt hash
        hashed_password = bcrypt.hashpw(NEW_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        print(f"Generated new hash for '{NEW_PASSWORD}': {hashed_password}")

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Update the user's password hash in the database
        cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (hashed_password, TARGET_EMAIL))
        conn.commit()

        if cursor.rowcount > 0:
            print(f"✅ Success: Password for {TARGET_EMAIL} updated in the database.")
            print(f"   You can now log in with email: {TARGET_EMAIL} and password: {NEW_PASSWORD}")
        else:
            print(f"❌ Failed: No user found with email {TARGET_EMAIL}. Check the email in TARGET_EMAIL variable.")

    except mysql.connector.Error as err:
        print(f"❌ Database Error: {err}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    update_password_in_db()