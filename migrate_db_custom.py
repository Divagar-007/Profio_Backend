from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:MyData18@localhost:5433/new_db")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("Checking and migrating database...")
    queries = [
        "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'applied';",
        "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS experience_years INTEGER;",
        "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS portfolio_link VARCHAR(500);",
        "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS note TEXT;"
    ]
    
    for q in queries:
        try:
            conn.execute(text(q))
            print(f"Executed: {q}")
        except Exception as e:
            print(f"Failed to execute {q}: {e}")
    
    conn.commit()
    print("Migration check complete.")
