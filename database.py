import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.getenv("PGDATABASE"),
            user=os.getenv("PGUSER"),
            password=os.getenv("PGPASSWORD"),
            host=os.getenv("PGHOST"),
            port=os.getenv("PGPORT")
        )
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS filters (
                trigger TEXT PRIMARY KEY,
                reply TEXT
            );
            CREATE TABLE IF NOT EXISTS stickers (
                user_id BIGINT,
                sticker_id TEXT,
                PRIMARY KEY (user_id, sticker_id)
            );
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                action TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    def add_filter(self, trigger, reply):
        self.cursor.execute(
            "INSERT INTO filters (trigger, reply) VALUES (%s, %s) ON CONFLICT (trigger) DO UPDATE SET reply = %s",
            (trigger, reply, reply)
        )
        self.conn.commit()

    def get_filters(self):
        self.cursor.execute("SELECT trigger, reply FROM filters")
        return self.cursor.fetchall()

    def remove_filter(self, trigger):
        self.cursor.execute("DELETE FROM filters WHERE trigger = %s", (trigger,))
        self.conn.commit()

    def add_sticker(self, user_id, sticker_id):
        self.cursor.execute(
            "INSERT INTO stickers (user_id, sticker_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, sticker_id)
        )
        self.conn.commit()

    def get_stickers(self, user_id):
        self.cursor.execute("SELECT sticker_id FROM stickers WHERE user_id = %s", (user_id,))
        return [row[0] for row in self.cursor.fetchall()]

    def log_action(self, user_id, action):
        self.cursor.execute(
            "INSERT INTO logs (user_id, action) VALUES (%s, %s)",
            (user_id, action)
        )
        self.conn.commit()

    def get_logs(self):
        self.cursor.execute("SELECT user_id, timestamp, action FROM logs ORDER BY timestamp DESC LIMIT 10")
        return self.cursor.fetchall()

    def __del__(self):
        self.cursor.close()
        self.conn.close()
