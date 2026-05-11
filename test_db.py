import mysql.connector
import os

config = {
    'host': 'mysql-28307541-digital-mitraz.i.aivencloud.com',
    'port': 3306,
    'user': 'avnadmin',
    'password': 'YOUR_PASSWORD',
    'database': 'YOUR_DB_NAME',
    'ssl_disabled': False
}

try:
    conn = mysql.connector.connect(**config)
    print("✅ Connection successful!")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")