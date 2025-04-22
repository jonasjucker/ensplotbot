import pytest
import sys
import os
import yaml

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import Database
from constants import VALID_SUMMARY_INTERVALS


@pytest.fixture(scope="module")
def db_instance():
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
    db_instance._execute_query_with_value(
        f"DELETE FROM activity_{db_instance._table_suffix}", ())
    db_instance._execute_query_with_value(
        f"DELETE FROM subscriptions_{db_instance._table_suffix}", ())
    yield
    # Clear the test tables after each test
    db_instance._execute_query_with_value(
        f"DELETE FROM activity_{db_instance._table_suffix}", ())
    db_instance._execute_query_with_value(
        f"DELETE FROM subscriptions_{db_instance._table_suffix}", ())


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


@pytest.mark.parametrize('interval', VALID_SUMMARY_INTERVALS)
def test_log_activity(db_instance, interval):
    db_instance.log_activity("login", 12345, "station1")
    db_instance.log_activity("login", 12335, "station1")
    db_instance.log_activity("bot-error", 13345, "unknown")
    db_instance.log_activity("send-plot", 83345, "station4")
    db_instance.log_activity("send-plot", 82345, "station4")
    db_instance.log_activity("send-plot", 84345, "station4")
    result = db_instance.get_activity_summary(interval)
    assert len(result) == 3
    expected_result = ['send-plot: 3', 'login: 2', 'bot-error: 1']
    assert result == expected_result


def test_log_activity_invalid_interval(db_instance):
    with pytest.raises(ValueError):
        db_instance.get_activity_summary("INVALID_INTERVAL")


def test_stations_with_subscribers(db_instance):
    # Add test data
    db_instance.add_subscription("station1", 12345)
    db_instance.add_subscription("station2", 67890)
    db_instance.add_subscription("station1", 54321)

    stations = db_instance.stations_with_subscribers()

    # Assert the result
    assert stations == ["station1", "station2"]


def test_get_subscriptions_by_station(db_instance):
    # Add test data
    db_instance.add_subscription("station1", 12345)
    db_instance.add_subscription("station1", 67890)
    db_instance.add_subscription("station2", 54321)

    users = db_instance.get_subscriptions_by_station("station1")

    assert users == [12345, 67890]

    # Test for a station with no subscriptions
    users = db_instance.get_subscriptions_by_station("station3")
    assert users == []


def test_subscription_summary(db_instance):
    # Add test data
    db_instance.add_subscription("station1", 12345)
    db_instance.add_subscription("station2", 67890)
    db_instance.add_subscription("station1", 54321)

    summary = db_instance.get_subscription_summary()

    assert summary == ["station1: 2", "station2: 1"]


def test_get_unique_subscribers(db_instance):
    # Add test data
    db_instance.add_subscription("station1", 12345)
    db_instance.add_subscription("station2", 67890)
    db_instance.add_subscription("station1", 54321)

    unique_subscribers = db_instance.count_unique_subscribers()

    assert unique_subscribers == 3
