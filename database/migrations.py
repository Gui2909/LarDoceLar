from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# Colunas que o código atual espera mas podem faltar em bancos criados antes.
_SCHEMA_PATCHES: list[tuple[str, str, str]] = [
    ("products", "is_active", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("orders", "status", "VARCHAR NOT NULL DEFAULT 'ABERTO'"),
    ("cash_flow", "order_id", "INTEGER"),
    ("cash_flow", "cash_session_id", "INTEGER"),
    ("cash_flow", "payment_method", "VARCHAR"),
]


def run_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, column, definition in _SCHEMA_PATCHES:
            if table not in tables:
                continue
            columns = {col["name"] for col in inspector.get_columns(table)}
            if column in columns:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
