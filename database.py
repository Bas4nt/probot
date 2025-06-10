import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv
import time
import logging

# Set up logging for database operations
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class Database:
    def __init__(self, bot=None):
        self.bot = bot
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self, retries=3, delay=5):
        attempt = 0
        while attempt < retries:
            try:
                if self.conn is None or self.conn.closed:
                    logger.info("Attempting to connect to PostgreSQL database...")
                    self.conn = psycopg2.connect(
                        dbname=os.getenv("PGDATABASE"),
                        user=os.getenv("PGUSER"),
                        password=os.getenv("PGPASSWORD"),
                        host=os.getenv("PGHOST"),
                        port=os.getenv("PGPORT")
                    )
                    self.cursor = self.conn.cursor()
                    logger.info("Successfully connected to PostgreSQL database.")
                    return  # Connection successful
            except psycopg2.Error as e:
                attempt += 1
                if attempt == retries:
                    logger.error(f"Failed to connect to database after {retries} attempts: {e}")
                    raise Exception(f"Failed to connect to database after {retries} attempts: {e}")
                logger.warning(f"Connection attempt {attempt} failed: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)

    def create_tables(self):
        self.connect()  # Ensure connection is active
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
        logger.info("Database tables created or verified.")

    def add_filter(self, trigger, reply):
        self.connect()
        self.cursor.execute(
            "INSERT INTO filters (trigger, reply) VALUES (%s, %s) ON CONFLICT (trigger) DO UPDATE SET reply = %s",
            (trigger, reply, reply)
        )
        self.conn.commit()

    def get_filters(self):
        self.connect()
        self.cursor.execute("SELECT trigger, reply FROM filters")
        return self.cursor.fetchall()

    def remove_filter(self, trigger):
        self.connect()
        self.cursor.execute("DELETE FROM filters WHERE trigger = %s", (trigger,))
        self.conn.commit()

    def add_sticker(self, user_id, sticker_id):
        self.connect()
        self.cursor.execute(
            "INSERT INTO stickers (user_id, sticker_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, sticker_id)
        )
        self.conn.commit()

    def get_stickers(self, user_id):
        self.connect()
        self.cursor.execute("SELECT sticker_id FROM stickers WHERE user_id = %s", (user_id,))
        return [row[0] for row in self.cursor.fetchall()]

    async def log_action(self, user_id, action):
        self.connect()
        self.cursor.execute(
            "INSERT INTO logs (user_id, action) VALUES (%s, %s)",
            (user_id, action)
        )
        self.conn.commit()
        if self.bot and os.getenv("LOG_CHAT_ID"):
            await self.bot.send_message(
                chat_id=os.getenv("LOG_CHAT_ID"),
                text=f"[{action}] by User {user_id}"
            )

    def get_logs(self):
        self.connect()
        self.cursor.execute("SELECT user_id, timestamp, action FROM logs ORDER BY timestamp DESC LIMIT 10")
        return self.cursor.fetchall()

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed.")
