import pytest
import sys
import os
import yaml

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import Database

@pytest.fixture(scope="module")
def db_instance():
    # Use the real configuration file for the test database
    
    config_file = "config.yml"
    if not os.path.exists(config_file):
        config = {
            "db": {
                "host": os.getenv("DB_HOST"),
                "user": os.getenv("DB_USER"),
                "password": os.getenv("DB_PASSWORD"),
                "database": os.getenv("DB_DATABASE"),
                "port": int(os.getenv("DB_PORT")),
            }
        }
        # Write the config to a file
        with open(config_file, "w") as f:
            yaml.dump(config, f)

    db = Database(config_file, table_suffix="test")
    yield db

@pytest.fixture(scope="function", autouse=True)
def setup_and_teardown(db_instance):
    # Clear the test tables before each test
    db_instance._execute_query_with_value(f"DELETE FROM activity_{db_instance._table_suffix}", ())
    db_instance._execute_query_with_value(f"DELETE FROM subscriptions_{db_instance._table_suffix}", ())
    yield
    # Clear the test tables after each test
    db_instance._execute_query_with_value(f"DELETE FROM activity_{db_instance._table_suffix}", ())
    db_instance._execute_query_with_value(f"DELETE FROM subscriptions_{db_instance._table_suffix}", ())

def test_add_subscription(db_instance):
    db_instance.add_subscription("station1", 12345)
    result = db_instance.get_subscriptions_by_user(12345)
    assert result == ["station1"]
    db_instance.add_subscription("station3", 12345)
    result = db_instance.get_subscriptions_by_user(12345)
    assert result == ["station1", "station3"]

def test_remove_subscription(db_instance):
    db_instance.add_subscription("station1", 12345)
    result = db_instance.get_subscriptions_by_user(12345)
    assert result == ["station1"]
    db_instance.remove_subscription("station1", 12345)
    result = db_instance.get_subscriptions_by_user(12345)
    assert result == []

def test_log_activity(db_instance):
    db_instance.log_activity("login", 12345, "station1")
    result = db_instance.get_activity_summary()
    assert result[0]["activity_type"] == "login"
    assert result[0]["count"] == 1