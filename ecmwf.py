import requests
import json
import datetime
import retry

import pandas as pd

from constants import ALL_EPSGRAM
from location import APILocation
from logger_config import logger


class EcmwfApi():

    def __init__(self, station_config):

        self._API_URL = "https://charts.ecmwf.int/opencharts-api/v1/"
        self._stations = [
            APILocation(**station_data) for station_data in station_config
        ]
        self._time_format = '%Y-%m-%dT%H:%M:%SZ'
        self._base_time = self._fetch_available_base_time(fallback=True,
                                                          timeshift=0)

        # for performance reasons we set to base_time from API-schema, can be wrong
        # so we need to check if it is valid after the init of all stations
        logger.info('base_time set to {}'.format(self._base_time))
        for Station in self._stations:
            Station.base_time = self._base_time

    def override_base_time_from_init(self):
        for Station in self._stations:
            latest_run = self._latest_confirmed_run(Station)
            if latest_run > Station.base_time:
                logger.info('Overriding {} base_time from {} to {}'.format(
                    Station.name, Station.base_time, latest_run))
                Station.upgrade_basetime(latest_run)

    def _first_guess_base_time(self):
        t_now = datetime.datetime.now()
        t_now_rounded = pd.Timestamp.now().round(freq='12h').to_pydatetime()

        # rounding ends up in future
        if t_now <= t_now_rounded:
            t_now_rounded = t_now_rounded - datetime.timedelta(hours=12)

        latest_run = t_now_rounded.strftime(self._time_format)
        logger.debug('latest run: {}'.format(latest_run))

        return latest_run

    def upgrade_basetime_global(self):
        try:
            new_base_time = self._fetch_available_base_time(fallback=False)
            if new_base_time != self._base_time:
                self._base_time = new_base_time
                logger.info('base_time updated to {}'.format(self._base_time))
        except ValueError:
            logger.debug('Upgrading base_time failed, keeping {}'.format(
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
        for eps_type in ALL_EPSGRAM:
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

    @retry.retry(tries=10, delay=0.5, logger=None)
    def _get_from_API_retry(self, link, raise_on_error=True):
        return self._get_with_request(link, raise_on_error)

    def _get_with_request(self, link, raise_on_error=True):
        get = '{}{}'.format(self._API_URL, link)
        logger.debug('GET {}'.format(get))
        result = requests.get(get)

        if not result.ok and raise_on_error:
            raise ValueError('Request failed for {}'.format(get))
        else:
            try:
                return result.json()
            except json.decoder.JSONDecodeError:
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
        logger.debug("image saved in {}".format(file))
        return file

    def download_plots(self, requested_stations):
        plots_for_broadcast = {}
        for Station in self._stations:
            if Station.name in requested_stations:
                plots_for_broadcast.update(self._download_plots(Station))

        return plots_for_broadcast

    def upgrade_basetime_stations(self):
        for Station in self._stations:
            self._upgrade_basetime_for_station(Station)

    def _upgrade_basetime_for_station(self, station):
        if self._new_forecast_available(station):

            # base_time for which all epsgrams are available
            confirmed_base_time = self._latest_confirmed_run(station)

            if confirmed_base_time == self._base_time:
                logger.debug('base_time for {} updated to {}'.format(
                    station.name, confirmed_base_time))

                # base_time needs update before fetch
                # if not updated, bot sends endless plots to users
                station.upgrade_basetime(confirmed_base_time)
            else:
                logger.debug('base_time for {} {} and {} are the same'.format(
                    station.name, station.base_time, confirmed_base_time))

    def download_latest_plots(self, requested_stations):
        plots_for_broadcast = {}
        for Station in self._stations:
            if Station.name in requested_stations and not Station.has_been_broadcasted:
                plots = self._download_plots(Station)
                if plots:
                    Station.has_been_broadcasted = True
                    plots_for_broadcast.update(plots)

        return plots_for_broadcast

    def _download_plots(self, Station):
        plots = {}
        eps = []
        if Station.plots_cached:
            plots[Station.name] = Station.all_plots
            logger.info(f'{Station.name}: Plots cached')
        else:
            logger.info(f'{Station.name}: Fetching plots')
            try:
                for type in ALL_EPSGRAM:
                    image_api = self._request_epsgram_link_for_station(
                        Station, type)
                    eps.append(
                        self._save_image_of_station(image_api, Station, type))
                plots[Station.name] = eps
                Station.plots_cached = True
            except ValueError as e:
                logger.warning('Could not fetch plots for {}'.format(
                    Station.name))
                plots.clear()

        return plots

    def _new_forecast_available(self, Station):
        return Station.base_time != self._base_time

    def cache_plots(self):
        uncached = set()
        for S in self._stations:
            if not S.plots_cached:
                uncached.add(S)
        if uncached:
            # only pick one element to not block the main thread
            s = uncached.pop()
            logger.info(f'Start caching for {s.name}')
            self._download_plots(s)
        else:
            logger.debug(f'All plots cached')
