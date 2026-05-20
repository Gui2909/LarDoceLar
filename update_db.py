from database.connection import SessionLocal
from sqlalchemy import text
db = SessionLocal()
db.execute(text("ALTER TABLE orders ADD COLUMN payment_status VARCHAR DEFAULT 'PAGO'"))
db.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR"))
db.commit()
print('Schema Updated')
