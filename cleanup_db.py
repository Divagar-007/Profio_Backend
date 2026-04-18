# cleanup.py
from sqlalchemy import text
from database.db import engine

def cleanup():
    with engine.connect() as conn:
        print("Dropping password_reset_otps table...")
        conn.execute(text("DROP TABLE IF EXISTS password_reset_otps CASCADE;"))
        print("Dropping phone_number column from users...")
        try:
            conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS phone_number;"))
            print("Successfully dropped column.")
        except Exception as e:
            print(f"Error dropping column: {e}")
        conn.commit()

if __name__ == "__main__":
    cleanup()
