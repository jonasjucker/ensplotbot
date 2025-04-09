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

                # subscriptions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id SERIAL PRIMARY KEY,
                        station TEXT NOT NULL,
                        user_id VARCHAR(50) NOT NULL
                    )
                """)
            connection.commit()
        except Exception as e:
            logger.error(f"{e} while creating tables")
        finally:
            connection.close()

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

                # subscriptions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id SERIAL PRIMARY KEY,
                        station TEXT NOT NULL,
                        user_id BIGINT NOT NULL,
                        UNIQUE (station, user_id)
                    )
                """)
            connection.commit()
        finally:
            connection.close()

    def add_subscription(self, station, user_id):
        sql = """
            INSERT INTO subscriptions (station, user_id)
            VALUES (%s, %s)
            ON CONFLICT (station, user_id) DO NOTHING
        """
        values = (station, user_id)
        self._execute_query_with_value(sql, values)

    def remove_subscription(self, station, user_id):
        sql = """
            DELETE FROM subscriptions
            WHERE station = %s AND user_id = %s
        """
        values = (station, user_id)
        self._execute_query_with_value(sql, values)

    def get_subscriptions_by_user(self, user_id):
        sql = """
            SELECT station
            FROM subscriptions
            WHERE user_id = %s
        """
        return self._select_with_values(sql, (user_id, ))

    def get_users_by_station(self, station):
        sql = """
            SELECT user_id
            FROM subscriptions
            WHERE station = %s
        """
        return self._select_with_values(sql, (station, ))

    def _select_with_values(self, sql, values):
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"{e} with SQL: {sql} and values: {values}")
        finally:
            connection.close()

    def log_activity(self, activity_type, user_id, station):
        sql = """
            INSERT INTO activity_log (activity_type, user_id, station, timestamp)
            VALUES (%s, %s, %s, %s)
        """
        values = (activity_type, user_id, station, datetime.now())
        self._execute_query_with_value(sql, values)

    def get_activity_summary(self):
        sql = """
            SELECT activity_type, COUNT(*) AS count
            FROM activity_log
            WHERE timestamp >= NOW() - INTERVAL '24 HOURS'
            GROUP BY activity_type
            ORDER BY count DESC
        """
        return self._select(sql)

    def _select(self, sql):
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"{e} with SQL: {sql}")
        finally:
            connection.close()

    def _execute_query_with_value(self, sql, values):
        connection = self._get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
            connection.commit()
        except Exception as e:
            logger.error(f"{e} with SQL: {sql} and values: {values}")
        finally:
            connection.close()
