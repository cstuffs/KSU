# manual_migrations.py

from extensions import db
from flask import Flask
import os

def run_migration():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///local_fallback.db")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        with db.engine.connect() as conn:
            # Check if column already exists before adding
            inspector = db.inspect(conn)
            columns = [col["name"] for col in inspector.get_columns("menu_item")]

            if "case_size" not in columns:
                conn.execute(db.text("ALTER TABLE menu_item ADD COLUMN case_size INTEGER DEFAULT 1"))

            if "reorder_point" not in columns:
                conn.execute(db.text("ALTER TABLE menu_item ADD COLUMN reorder_point INTEGER DEFAULT 0"))

            print("✅ Migration complete.")

if __name__ == "__main__":
    run_migration()
