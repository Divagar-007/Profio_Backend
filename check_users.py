# check_users.py
from database.db import engine
from sqlalchemy import text

def check():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT name, email, phone_number FROM users"))
        users = res.fetchall()
        print(f"Total Users: {len(users)}")
        for u in users:
            print(f"Name: {u[0]}, Email: {u[1]}, Phone: {u[2]}")

if __name__ == "__main__":
    check()
