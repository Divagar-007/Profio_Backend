from database.db import engine
from sqlalchemy import text

def add_column():
    with engine.connect() as con:
        # Check if column exists first
        try:
            con.execute(text("SELECT banner_picture FROM users LIMIT 1"))
            print("Column 'banner_picture' already exists.")
            return
        except Exception as e:
            print("Column missing, adding it...")
            
    # Open new connection block to be in a fresh transaction state
    with engine.connect() as con2:
        try:
            con2.execute(text("ALTER TABLE users ADD COLUMN banner_picture VARCHAR(500);"))
            con2.commit()
            print("Successfully added banner_picture column.")
        except Exception as e2:
            print(f"Error adding column: {e2}")

if __name__ == "__main__":
    add_column()
