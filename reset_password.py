import mysql.connector
import bcrypt
import os
from dotenv import load_dotenv

# Load your database credentials from the .env file
load_dotenv()

def reset_superadmin():
    try:
        # Connect to your new database
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'mitra_db'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD') # Uses your local MySQL password
        )
        cursor = conn.cursor()

        # The account we want to fix
        target_email = 'superadmin@mitraz.com'
        new_password = 'admin123'

        # Generate a fresh, valid encrypted hash
        print("Encrypting new password...")
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Update the database
        cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (hashed_pw, target_email))
        conn.commit()

        if cursor.rowcount > 0:
            print(f"✅ SUCCESS! Password for '{target_email}' has been reset to '{new_password}'.")
        else:
            print(f"❌ ERROR: Could not find user '{target_email}' in the database. Did you run the schema.sql file?")

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    reset_superadmin()