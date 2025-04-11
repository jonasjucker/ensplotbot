import pytest
import sys
import os
import yaml

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot import PlotBot


@pytest.fixture
def bot(station_config):
    from bot import PlotBot
    token = '9999999999:BBBBBBBRBBBBBBBBBBBBBBBBBBBBBBBBBBB'
    return PlotBot(token, station_config, 'test/backup')


@pytest.fixture
def station_config():
    stations = """
- name: Zürich
  region: Zurich
  lat: 47.3667
  lon: 8.55

- name: Basel
  region: Basilea
  lat: 47.5584
  lon: 7.57327

- name: Bern
  region: Canton Berne
  lat: 47.5056
  lon: 8.72413
    """
    return yaml.safe_load(stations)


def test_register_subscription(bot):
    id1 = 123
    bot_data = bot._dp.bot_data
    bot._register_subscription(id1, 'Bern', bot_data)
    assert id1 in bot_data['Bern']
    assert id1 in bot._subscriptions['Bern']


def test_has_new_subscribers_waiting(bot):
    assert not bot.has_new_subscribers_waiting()
    bot._register_subscription(123, 'Bern', bot._dp.bot_data)
    assert bot.has_new_subscribers_waiting()


def test_stations_of_new_subscribers(bot):
    bot._register_subscription(123, 'Bern', bot._dp.bot_data)
    assert bot.stations_of_new_subscribers() == ['Bern']
    bot._register_subscription(324, 'Basel', bot._dp.bot_data)
    assert bot.stations_of_new_subscribers() == ['Basel', 'Bern']
    bot._register_subscription(123, 'Zürich', bot._dp.bot_data)
    assert bot.stations_of_new_subscribers() == ['Zürich', 'Basel', 'Bern']



def test_revoke_subscription(bot):
    id1 = 123
    id2 = 234
    bot_data = bot._dp.bot_data
    bot_data['Bern'].add(id1)
    bot_data['Bern'].add(id2)
    assert id1 in bot_data['Bern']
    assert id2 in bot_data['Bern']
    bot._revoke_subscription(id1, 'Bern', bot_data)
    assert id1 not in bot_data['Bern']
    assert id2 in bot_data['Bern']


def test_available_locations(bot):
    assert bot._available_locations() == [
        '_Available locations_', '', '*Basilea*', '- Basel', '',
        '*Canton Berne*', '- Bern', '', '*Zurich*', '- Zürich'
    ]


def test_stations_with_subscribers(bot):
    bot._register_subscription(123, 'Bern', bot._dp.bot_data)
    bot._register_subscription(124, 'Bern', bot._dp.bot_data)
    bot._register_subscription(125, 'Zürich', bot._dp.bot_data)
    assert bot.stations_with_subscribers() == ['Bern', 'Zürich']
    bot._revoke_subscription(123, 'Bern', bot._dp.bot_data)
    assert bot.stations_with_subscribers() == ['Bern', 'Zürich']
    bot._revoke_subscription(124, 'Bern', bot._dp.bot_data)
    assert bot.stations_with_subscribers() == ['Zürich']
    bot._revoke_subscription(125, 'Zürich', bot._dp.bot_data)
    assert bot.stations_with_subscribers() == []
