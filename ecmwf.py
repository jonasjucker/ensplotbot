import requests
import json
import datetime
import time
import logging
import retry

import pandas as pd

d10_plume = 'classical_plume'
d10_eps = 'classical_10d'
d15_eps = 'classical_15d'

ALL_EPSGRAM = [d10_plume, d10_eps, d15_eps]


class EcmwfApi():

    def __init__(self, station_config):

        class Station():

            def __init__(self, name, lat, lon, region, api_name=None):
                self.name = name
                self.api_name = name if api_name is None else api_name
                self.lat = lat
                self.lon = lon
                self.region = region
                self.base_time = None

        self._API_URL = "https://charts.ecmwf.int/opencharts-api/v1/"
        self._stations = [
            Station(**station_data) for station_data in station_config
        ]
        self._epsgrams = ALL_EPSGRAM
        self._time_format = '%Y-%m-%dT%H:%M:%SZ'
        self._base_time = self._fetch_available_base_time(fallback=True,
                                                          timeshift=0)

        self._plots_for_broadcast = {}

        # for performance reasons we set to base_time from API-schema, can be wrong
        # so we need to check if it is valid after the init of all stations
        logging.info('base_time set to {}'.format(self._base_time))
        for Station in self._stations:
            Station.base_time = self._base_time

    def override_base_time_from_init(self):
        for Station in self._stations:
            latest_run = self._latest_confirmed_run(Station)
            if latest_run > Station.base_time:
                logging.info('Overriding {} base_time from {} to {}'.format(
                    Station.name, Station.base_time, latest_run))
                Station.base_time = latest_run

    def _first_guess_base_time(self):
        t_now = datetime.datetime.now()
        t_now_rounded = pd.Timestamp.now().round(freq='12H').to_pydatetime()

        # rounding ends up in future
        if t_now <= t_now_rounded:
            t_now_rounded = t_now_rounded - datetime.timedelta(hours=12)

        latest_run = t_now_rounded.strftime(self._time_format)
        logging.debug('latest run: {}'.format(latest_run))

        return latest_run

    def upgrade_basetime(self):
        try:
            new_base_time = self._fetch_available_base_time(fallback=False)
            if new_base_time != self._base_time:
                self._base_time = new_base_time
                logging.info('base_time updated to {}'.format(self._base_time))
        except ValueError:
            logging.debug('Upgrading base_time failed, keeping {}'.format(
                self._base_time))
            pass

    def _fetch_available_base_time(self, fallback=False, timeshift=0):
        link = "schema/?product=opencharts_meteogram&package=openchart"
        try:
            run = self._get_from_API(
                link, retry=False)['paths']['/products/opencharts_meteogram/'][
                    'get']['parameters'][1]['schema']['default']
        except ValueError:
            if fallback:
                run = self._first_guess_base_time()
            else:
                raise ValueError('No available base_time found')
        run_datetime = datetime.datetime.strptime(run, self._time_format)
        run_datetime -= datetime.timedelta(hours=timeshift)
        run = run_datetime.strftime(self._time_format)
        return run

    def _latest_confirmed_run(self, station):
        # check if forecast for basetime is available for all epsgrams
        base_time = set()
        for eps_type in self._epsgrams:
            try:
                self._get_API_data_for_epsgram(station,
                                               self._base_time,
                                               eps_type,
                                               raise_on_error=True,
                                               retry=False)
                base_time.add(self._base_time)
            except ValueError as e:
                # base time - 12h should be available
                base_time_minus_12h = (datetime.datetime.strptime(
                    self._base_time, self._time_format) -
                                       datetime.timedelta(hours=12)).strftime(
                                           self._time_format)
                base_time.add(base_time_minus_12h)

        # if there are multiple base_time, take the oldest
        if len(base_time) > 1:
            return min(base_time)
        else:
            return base_time.pop()

    def _get_from_API(self, link, retry=True, raise_on_error=True):
        if retry:
            return self._get_from_API_retry(link, raise_on_error)
        else:
            return self._get_from_API_no_retry(link, raise_on_error)

    def _get_from_API_no_retry(self, link, raise_on_error=True):
        return self._get_with_request(link, raise_on_error)

    @retry.retry(tries=20, delay=1)
    def _get_from_API_retry(self, link, raise_on_error=True):
        return self._get_with_request(link, raise_on_error)

    def _get_with_request(self, link, raise_on_error=True):
        get = '{}{}'.format(self._API_URL, link)
        logging.debug('GET {}'.format(get))
        result = requests.get(get)

        if not result.ok and raise_on_error:
            raise ValueError('Request failed for {}'.format(get))
        else:
            if result.status_code == 403:
                logging.info('403 Forbidden for {}'.format(get))
                raise ValueError('403 Forbidden for {}'.format(get))
            else:
                try:
                    return result.json()
                except json.decoder.JSONDecodeError:
                    logging.info('JSONDecodeError for {}'.format(get))
                    raise ValueError('JSONDecodeError for {}'.format(get))

    def _get_API_data_for_epsgram(self,
                                  station,
                                  base_time,
                                  eps_type,
                                  raise_on_error=True,
                                  retry=True):
        link = 'products/opencharts_meteogram/?epsgram={}&base_time={}&station_name={}&lat={}&lon={}'.format(
            eps_type, base_time, station.api_name, station.lat, station.lon)

        return self._get_from_API(link,
                                  raise_on_error=raise_on_error,
                                  retry=retry)

    def _request_epsgram_link_for_station(self, station, eps_type):
        data = self._get_API_data_for_epsgram(station,
                                              station.base_time,
                                              eps_type,
                                              raise_on_error=True,
                                              retry=True)
        return data["data"]["link"]["href"]

    def _save_image_of_station(self, image_api, station, eps_type):
        image = requests.get(image_api)
        file = "./{}_{}.png".format(station.name, eps_type)
        with open(file, "wb") as img:
            img.write(image.content)
        logging.info("image saved in {}".format(file))
        return file

    def download_plots(self, requested_stations):
        for Station in self._stations:
            if Station.name in requested_stations:
                self._download_plots(Station)

        # copy because we reset _plots_for_broadcast now
        plots_for_broadcast = self._plots_for_broadcast.copy()
        self._plots_for_broadcast = {}

        return plots_for_broadcast

    def download_latest_plots(self):
        for Station in self._stations:
            if self._new_forecast_available(Station):

                # base_time for which all epsgrams are available
                confirmed_base_time = self._latest_confirmed_run(Station)

                if confirmed_base_time == self._base_time:
                    logging.debug('base_time for {} updated to {}'.format(
                        Station.name, confirmed_base_time))

                    # base_time needs update before fetch
                    # if not updated, bot sends endless plots to users
                    Station.base_time = confirmed_base_time
                    self._download_plots(Station)
                else:
                    logging.debug(
                        'base_time for {} {} and {} are the same'.format(
                            Station.name, Station.base_time,
                            confirmed_base_time))

        # copy because we reset _plots_for_broadcast now
        plots_for_broadcast = self._plots_for_broadcast.copy()
        self._plots_for_broadcast = {}

        return plots_for_broadcast

    def _download_plots(self, Station):
        logging.info('Fetch plots for {}'.format(Station.name))
        plots = []
        try:
            for type in self._epsgrams:
                image_api = self._request_epsgram_link_for_station(
                    Station, type)
                plots.append(
                    self._save_image_of_station(image_api, Station, type))
        except ValueError as e:
            logging.warning(
                'Error while fetching plots for {}, skipping...'.format(
                    Station.name))
            plots = []

        self._plots_for_broadcast[Station.name] = plots

    def _new_forecast_available(self, Station):
        return Station.base_time != self._base_time
