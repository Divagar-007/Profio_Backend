# migrate.py
from sqlalchemy import text
from database.db import engine, Base
import models.models # ensure models are registered

def migrate():
    with engine.connect() as conn:
        print("Adding phone_number column to users table...")
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20) UNIQUE;"))
            conn.commit()
            print("Successfully added phone_number column.")
        except Exception as e:
            print(f"Error adding column: {e}")

    print("Creating all tables (including password_reset_otps)...")
    Base.metadata.create_all(bind=engine)
    print("Done.")

if __name__ == "__main__":
    migrate()
