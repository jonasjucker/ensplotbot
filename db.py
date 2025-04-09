import yaml
import psycopg2
from datetime import datetime

class Database:
    def __init__(self, config_file):
        self.config = yaml.safe_load(open(config_file))
        self._create_tables()

    def _get_db_connection(self):
        connection = psycopg2.connect(
            host=self.config['db']['host'],
            user=self.config['db']['user'],
            password=self.config['db']['password'],
            dbname=self.config['db']['database'],
            port=self.config['db']['port']
            )
        return connection

    def _create_tables(self):
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                # activity_log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS activity_log (
                        id SERIAL PRIMARY KEY,
                        activity_type VARCHAR(50) NOT NULL,
                        user_id VARCHAR(50) NOT NULL,
                        station TEXT,
                        timestamp TIMESTAMP NOT NULL
                    )
                """)
            connection.commit()
        finally:
            connection.close()


    def log_activity(self, activity_type, user_id, station):
        sql = """
            INSERT INTO activity_log (activity_type, user_id, station, timestamp)
            VALUES (%s, %s, %s, %s)
        """
        values = (activity_type, user_id, station, datetime.now())
        self._insert(sql, values)

    def _insert(self, sql, values):
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
            connection.commit()
        finally:
            connection.close()
