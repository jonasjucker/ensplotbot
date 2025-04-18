import pytest
import sys
import os
import yaml

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot import PlotBot


@pytest.fixture(scope="module")
def bot(station_config):
      config_file = "test_config.yml"
      config = {
          "bot": {
              "token": '9999999999:BBBBBBBRBBBBBBBBBBBBBBBBBBBBBBBBBBB',
              "admin_ids": [123456789, 987654321],
          }
      }
      # Write the config to a file
      with open(config_file, "w") as f:
          yaml.dump(config, f)

      yield PlotBot(config_file, station_config)

      # Clear the test config file after the test
      os.remove(config_file)



@pytest.fixture(scope="module")
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


def test_available_locations(bot):
    assert bot._available_locations() == [
        '_Available locations_', '', '*Basilea*', '- Basel', '',
        '*Canton Berne*', '- Bern', '', '*Zurich*', '- Zürich'
    ]
