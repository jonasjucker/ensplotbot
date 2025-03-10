import pytest
import yaml
import sys
import os
from unittest.mock import patch
from datetime import datetime

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ecmwf import EcmwfApi


@pytest.fixture
def ecmwf(station_config):
    return EcmwfApi(station_config)


@pytest.fixture
def station_config():
    with open('stations.yaml', 'r') as file:
        station_config = yaml.safe_load(file)
    return station_config


def test_station_config_has_valid_entries(station_config):
    for station in station_config:
        assert 'name' in station and isinstance(
            station['name'], str), f'{station["name"]} is not a string'
        assert 'lat' in station and isinstance(
            station['lat'], float), f'{station["lat"]} is not a float'
        assert 'lon' in station and isinstance(
            station['lon'], float), f'{station["lon"]} is not a float'


def test_ecmwf_api_init_with_station_config(station_config):
    ecmwf = EcmwfApi(station_config)
    assert ecmwf is not None


def test_fetch_available_base_time(ecmwf):
    base_time = ecmwf._fetch_available_base_time(fallback=True, timeshift=0)
    assert isinstance(base_time, str), "base_time is not a string"
    try:
        datetime.strptime(base_time, ecmwf._time_format)
    except ValueError:
        pytest.fail(f"base_time '{base_time}' is not a valid datetime")


@pytest.mark.parametrize("timeshift", [3, 12, 24, -12])
def test_fetch_available_base_time_with_timeshift_of(ecmwf, timeshift):
    base_time_no_shift = ecmwf._fetch_available_base_time(fallback=True,
                                                          timeshift=0)
    base_time = ecmwf._fetch_available_base_time(fallback=True,
                                                 timeshift=timeshift)
    # check that the time is shifted by the correct amount
    base_time_dt = datetime.strptime(base_time, ecmwf._time_format)
    base_time_no_shift_dt = datetime.strptime(base_time_no_shift,
                                              ecmwf._time_format)
    assert (base_time_no_shift_dt -
            base_time_dt).total_seconds() == timeshift * 3600


def test_fetch_available_base_time_with_fallback(ecmwf):
    with patch.object(EcmwfApi, '_get_from_API', side_effect=ValueError):
        base_time = ecmwf._fetch_available_base_time(fallback=True,
                                                     timeshift=0)
        assert isinstance(base_time, str), "base_time is not a string"
        try:
            datetime.strptime(base_time, ecmwf._time_format)
        except ValueError:
            pytest.fail(f"base_time '{base_time}' is not a valid datetime")


def test_fetch_available_base_time_no_fallback(ecmwf):
    with patch.object(EcmwfApi, '_get_from_API', side_effect=ValueError):
        with pytest.raises(ValueError, match="No available base_time found"):
            ecmwf._fetch_available_base_time(fallback=False, timeshift=0)


def test_fetch_available_base_time_timeshift_for_fallback(ecmwf):
    timeshift = 12
    with patch.object(EcmwfApi, '_get_from_API', side_effect=ValueError):
        base_time = ecmwf._fetch_available_base_time(fallback=True,
                                                     timeshift=timeshift)
        base_time_no_shift = ecmwf._fetch_available_base_time(fallback=True,
                                                              timeshift=0)
        base_time_dt = datetime.strptime(base_time, ecmwf._time_format)
        base_time_no_shift_dt = datetime.strptime(base_time_no_shift,
                                                  ecmwf._time_format)
        assert (base_time_no_shift_dt -
                base_time_dt).total_seconds() == timeshift * 3600


def test_upgrade_base_time(ecmwf):
    # override with based time shifted by 12 hours
    ecmwf._base_time = ecmwf._fetch_available_base_time(fallback=True,
                                                        timeshift=12)
    base_time_shifted = ecmwf._base_time
    ecmwf.upgrade_basetime()
    assert ecmwf._base_time != base_time_shifted, "base_time was not updated"


def test_upgrade_base_time_if_api_request_fails(ecmwf):
    # override with based time shifted by 12 hours
    ecmwf._base_time = ecmwf._fetch_available_base_time(fallback=True,
                                                        timeshift=12)
    base_time_shifted = ecmwf._base_time
    with patch.object(EcmwfApi,
                      '_fetch_available_base_time',
                      side_effect=ValueError):
        ecmwf.upgrade_basetime()
    assert ecmwf._base_time == base_time_shifted, "base_time was updated but should not have been"


def test_new_forecast_available_for_same_basetimes(ecmwf):
    # station and ecmwd.base_time are set to the same value
    for Station in ecmwf._stations:
        assert ecmwf._new_forecast_available(
            Station
        ) == False, f"New forecast should not be available for {Station.name}"


def test_new_forecast_available_for_different_basetimes(ecmwf):
    ecmwf._base_time = ecmwf._fetch_available_base_time(fallback=True,
                                                        timeshift=12)
    # station and ecmwd.base_time are set to different values
    for Station in ecmwf._stations:
        assert ecmwf._new_forecast_available(
            Station
        ) == True, f"New forecast should be available for {Station.name}"


@pytest.mark.parametrize("station", ['Tschiertschen', 'Elm'])
def test_latest_confirmed_run_for(ecmwf, station):
    for Station in ecmwf._stations:
        if Station.name == station:
            latest_run = ecmwf._latest_confirmed_run(Station)
            assert isinstance(latest_run, str), "latest_run is not a string"
            try:
                datetime.strptime(latest_run, ecmwf._time_format)
            except ValueError:
                pytest.fail(
                    f"latest_run '{latest_run}' is not a valid datetime")


@pytest.mark.parametrize("station", ['Winterthur'])
def test_latest_confirmed_run_with_base_time_48_h_in_past_for(ecmwf, station):
    base_time_at_init = ecmwf._base_time
    ecmwf._base_time = ecmwf._fetch_available_base_time(fallback=True,
                                                        timeshift=48)
    for Station in ecmwf._stations:
        if Station.name == station:
            latest_run = ecmwf._latest_confirmed_run(Station)
            assert base_time_at_init != latest_run, "latest_confirmed_run should be in far past"
            assert ecmwf._base_time == latest_run, "latest_confirmed_run should be identical to base_time"


def test_latest_confirmed_run_with_base_time_for_api_fail(ecmwf):
    for Station in ecmwf._stations:
        Station.base_time = ecmwf._fetch_available_base_time(fallback=True,
                                                             timeshift=24)
        with patch.object(EcmwfApi,
                          '_get_API_data_for_epsgram',
                          side_effect=ValueError):
            latest_run = ecmwf._latest_confirmed_run(Station)
        assert Station.base_time == latest_run, "latest_confirmed_run should be identical to base_time of station"
