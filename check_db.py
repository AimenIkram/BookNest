"""
BookNest Database Connectivity Verification Script
Tests Django's MySQL connection, database selection, and version retrieval.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from django.db.utils import OperationalError


def verify_connection():
    print("Testing connection to MySQL from Django...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION();")
            version = cursor.fetchone()
            
            cursor.execute("SELECT DATABASE();")
            current_db = cursor.fetchone()
            
            cursor.execute("SELECT USER();")
            current_user = cursor.fetchone()

        print("\n==========================================")
        print("  DATABASE CONNECTION SUCCESSFUL!")
        print("==========================================")
        print(f"  MySQL Server Version : {version[0]}")
        print(f"  Active Database      : {current_db[0]}")
        print(f"  Connected User       : {current_user[0]}")
        print("==========================================\n")
        return True
    except OperationalError as e:
        print("\n==========================================")
        print("  DATABASE CONNECTION FAILED")
        print("==========================================")
        print(f"  Error Details: {e}")
        print("==========================================\n")
        return False


if __name__ == "__main__":
    verify_connection()
