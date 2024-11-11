from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings

DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# create db
def create_database():
    """Ensuring the tables are created only once"""
try:
    inspector = inspect(engine)
    if not inspector.get_table_names():  # Check if tables already exist
        print("Setting up database tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created.")
except Exception as e:
    print(f"Database connectio failed: {e}")

# the dependancy
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

