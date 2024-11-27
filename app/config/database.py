from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

from app.config.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL

# Database engine and session
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_database():
    """
    Initialize the database by creating tables if they don't exist.
    """
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        if not existing_tables:
            logger.info("Creating database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialized successfully.")
        else:
            logger.info(f"Tables already exist: {existing_tables}. Skipping creation.")
    except Exception as e:
        logger.error(f"Error initializing the database: {e}")
        raise

# Database dependency
def get_db():
    """
    Provide a transactional scope around a series of operations.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
