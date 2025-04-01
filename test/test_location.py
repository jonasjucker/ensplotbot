import pytest
import yaml
import sys
import os

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from location import APILocation
from constants import ALL_EPSGRAM


@pytest.fixture
def station_config():
    with open('stations.yaml', 'r') as file:
        station_config = yaml.safe_load(file)
    return station_config


def test_station_config_has_valid_entries(station_config):
    for station in station_config:
        assert 'name' in station and isinstance(
            station['name'], str), f'{station["name"]} is not a string'
        if 'api_name' in station:
            assert 'api_name' in station and isinstance(
                station['api_name'],
                str), f'{station["api_name"]} is not a string'
        assert 'lat' in station and isinstance(
            station['lat'], float), f'{station["lat"]} is not a float'
        assert 'lon' in station and isinstance(
            station['lon'], float), f'{station["lon"]} is not a float'
        assert 'region' in station and isinstance(
            station['region'], str), f'{station["region"]} is not a string'


def test_station_config_has_valid_region(station_config):
    regions = [
        'Grisons', 'Glarus', 'Zurich', 'Basilea', 'Ticino', "Romandie",
        "Central Switzerland", "Valais", "Canton Berne", "Eastern Switzerland",
        "Aargau/Solothurn"
    ]
    for station in station_config:
        assert station[
            'region'] in regions, f"{station['region']} is not a valid region"


def test_station_config_has_no_conflict_with_name_and_region(station_config):
    names = {station['name'] for station in station_config}
    for station in station_config:
        assert station[
            'region'] not in names, f"{station['region']} is already a station name"


def test_init_location():
    location = APILocation(name="TestStation",
                           lat=47.0,
                           lon=8.0,
                           region="Zurich")
    assert location.name == "TestStation"
    assert location.lat == 47.0
    assert location.lon == 8.0
    assert location.region == "Zurich"
    assert location.base_time is None
    assert location.has_been_broadcasted is True
    assert location.plots_cached is False
    assert location.all_plots == [
        f'./TestStation_{i}.png' for i in ALL_EPSGRAM
    ]


def test_upgrade_basetime():
    location = APILocation(name="TestStation",
                           lat=47.0,
                           lon=8.0,
                           region="Zurich")
    location.upgrade_basetime("2023-10-01 12:00")
    assert location.base_time == "2023-10-01 12:00"
    assert location.has_been_broadcasted is False
    assert location.plots_cached is False
