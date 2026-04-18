from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:MyData18@localhost:5433/new_db")
engine = create_engine(DATABASE_URL)

print("Checking and updating NotificationType enum values...")
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    try:
        # Check current labels
        res = conn.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'notificationtype';"))
        labels = [r[0] for r in res]
        print(f"Current labels: {labels}")
        
        if 'job_application' not in labels:
            print("Adding 'job_application' to NotificationType enum...")
            conn.execute(text("ALTER TYPE notificationtype ADD VALUE 'job_application';"))
            print("Successfully added! ✓")
        else:
            print("'job_application' already exists or type is not PG enum.")
            
    except Exception as e:
        print(f"Error checking/altering enum: {e}")
        # Sometimes it's just a string column instead of a native enum in some setups, but Profio uses SAEnum
