import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DB_URI = os.getenv("DATABASE_URL")
if not DB_URI:
    raise ValueError("DATABASE_URL tidak ditemukan di .env")

engine = create_engine(DB_URI)

def execute_sql_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    with engine.begin() as conn:
        conn.execute(text(sql))
    print(f"Berhasil menjalankan {filename}")

if __name__ == "__main__":
    print("Mempersiapkan database...")
    execute_sql_file('script1.sql')
    print("Database siap!")
