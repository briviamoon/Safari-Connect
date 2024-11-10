from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://safariconnect:1Amodung%40%21.@192.168.0.102:5432/captive_portal"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# create db
def create_database():
    #Ensuring the tables are created only once
    inspector = inspect(engine)
    if not inspector.get_table_names():  # Check if tables already exist
        print("Setting up database tables...")
        Base.metadata.create_all(bind=engine)
        print("Tables created.")

try:
    connection = engine.connect()
    print("DataBase Exists and Is connected successfully")
except Exception as e:
    print(f"Database connectio failed: {e}")

# the dependancy
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

