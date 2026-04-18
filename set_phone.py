# set_phone.py
import sys
from sqlalchemy import text
from database.db import engine

def set_phone(email, phone):
    with engine.connect() as conn:
        print(f"Updating phone for {email} to {phone}...")
        try:
            res = conn.execute(text("UPDATE users SET phone_number = :phone WHERE email = :email"), {"phone": phone, "email": email})
            conn.commit()
            if res.rowcount > 0:
                print("Successfully updated.")
            else:
                print("User not found.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python set_phone.py <email> <phone>")
    else:
        set_phone(sys.argv[1], sys.argv[2])
