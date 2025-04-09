import yaml
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from logger_config import logger


class Database:

    def __init__(self, config_file):
        self.config = yaml.safe_load(open(config_file))
        self._create_tables()

    def _get_db_connection(self):
        connection = psycopg2.connect(host=self.config['db']['host'],
                                      user=self.config['db']['user'],
                                      password=self.config['db']['password'],
                                      dbname=self.config['db']['database'],
                                      port=self.config['db']['port'],
                                      cursor_factory=DictCursor)
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

    def get_activity_summary(self):
        sql = """
            SELECT activity_type, COUNT(*) AS count
            FROM activity_log
            WHERE timestamp >= NOW() - INTERVAL '24 HOURS'
            GROUP BY activity_type
            ORDER BY count DESC
        """
        activity = self._select(sql)
        summary = []
        summary.append("\nActivity Summary:")
        summary.append("---------------")
        for record in activity:
            summary.append(f"{record['activity_type']}: {record['count']}")
        return summary

    def _select(self, sql):
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()
        finally:
            connection.close()

    def _insert(self, sql, values):
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
            connection.commit()
        finally:
            connection.close()
