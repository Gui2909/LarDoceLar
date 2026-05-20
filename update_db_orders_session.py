from database.connection import engine
from sqlalchemy import text

def update_schema():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE orders ADD COLUMN cash_session_id INTEGER;"))
            conn.commit()
            print("Schema Updated: cash_session_id added")
        except Exception as e:
            print("Error or already updated:", e)

if __name__ == "__main__":
    update_schema()
