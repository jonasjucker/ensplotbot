import yaml
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from logger_config import logger


class Database:

    def __init__(self, config_file, table_suffix=None):
        self.config = yaml.safe_load(open(config_file))
        self._table_suffix = self.config['db']['table_suffix'] if table_suffix is None else 'test'
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
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS activity_{self._table_suffix} (
                        id SERIAL PRIMARY KEY,
                        activity_type VARCHAR(50) NOT NULL,
                        user_id VARCHAR(50) NOT NULL,
                        station TEXT,
                        timestamp TIMESTAMP NOT NULL
                    )
                """)

                # subscriptions table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS subscriptions_{self._table_suffix} (
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
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS activity_{self._table_suffix} (
                        id SERIAL PRIMARY KEY,
                        activity_type VARCHAR(50) NOT NULL,
                        user_id VARCHAR(50) NOT NULL,
                        station TEXT,
                        timestamp TIMESTAMP NOT NULL
                    )
                """)

                # subscriptions table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS subscriptions_{self._table_suffix} (
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
        sql = f"""
            INSERT INTO subscriptions_{self._table_suffix} (station, user_id)
            VALUES (%s, %s)
            ON CONFLICT (station, user_id) DO NOTHING
        """
        values = (station, user_id)
        self._execute_query_with_value(sql, values)

    def remove_subscription(self, station, user_id):
        sql = f"""
            DELETE FROM subscriptions_{self._table_suffix}
            WHERE station = %s AND user_id = %s
        """
        values = (station, user_id)
        self._execute_query_with_value(sql, values)

    def _get_subscriptions_by_user(self, user_id):
        sql = f"""
            SELECT station
            FROM subscriptions_{self._table_suffix}
            WHERE user_id = %s
        """
        return self._select_with_values(sql, (user_id, ))

    def get_subscriptions_by_user(self, user_id) -> list[str]:
        subscriptions = self._get_subscriptions_by_user(user_id)
        if subscriptions:
            return sorted(
                [subscription['station'] for subscription in subscriptions])
        else:
            return []

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
        sql = f"""
            INSERT INTO activity_{self._table_suffix} (activity_type, user_id, station, timestamp)
            VALUES (%s, %s, %s, %s)
        """
        values = (activity_type, user_id, station, datetime.now())
        self._execute_query_with_value(sql, values)

    def get_activity_summary(self):
        sql = f"""
            SELECT activity_type, COUNT(*) AS count
            FROM activity_{self._table_suffix}
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
