from sqlalchemy import create_engine, MetaData

DATABASE_URL = "postgresql://safariconnect:1Amodung%40%21.@192.168.0.100:5432/safaridb"
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Test connection
try:
    with engine.connect() as connection:
        print("Database connected successfully.")
except Exception as e:
    print(f"Error connecting to database: {e}")
