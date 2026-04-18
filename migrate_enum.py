import sqlalchemy
from database.db import engine

def migrate():
    with engine.connect() as conn:
        try:
            # PostgreSQL command to add a value to an enum type
            # Note: Cannot run inside a transaction block in some versions,
            # so we might need to commit first or use AUTOCOMMIT.
            # Using execution_options(isolation_level="AUTOCOMMIT") is the safest way.
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(sqlalchemy.text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'connection_rejected';"))
            print("Successfully added 'connection_rejected' to notificationtype enum.")
        except Exception as e:
            print(f"Error or Enum value already exists: {e}")

if __name__ == "__main__":
    migrate()
