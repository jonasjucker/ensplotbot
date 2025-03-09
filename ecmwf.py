import requests
import json
import datetime
import time
import logging
import re
import retry

import pandas as pd


d10_plume = 'classical_plume'
d10_eps = 'classical_10d'
d15_eps = 'classical_15d'

ALL_EPSGRAM = [d10_plume,d10_eps,d15_eps] 

class EcmwfApi():
    def __init__(self,station_config):
        
        class Station():
            def __init__(self,name,lat,lon):
                self.name = name
                self.lat = lat
                self.lon = lon
                self.base_time = None

        self._API_URL = "https://charts.ecmwf.int/opencharts-api/v1/" 
        self._stations = [Station(**station_data) for station_data in station_config]
        self._epsgrams = ALL_EPSGRAM

        self._plots_for_broadcast = {}

        # populate stations with valid run
        for Station in self._stations:
            Station.base_time = self._latest_confirmed_run(Station)
            logging.debug('init {} with base_time {}'.format(Station.name,Station.base_time))


    def _extract_available_base_time(self,msg):
        pattern = r"Current available base_time \['([^']+)'"
        match = re.search(pattern, msg[0])
        if match:
            return match.group(1)
        else:
            raise ValueError('No available base_time found')


    def _first_guess_base_time(self):
        t_now = datetime.datetime.now()
        t_now_rounded = pd.Timestamp.now().round(freq='12H').to_pydatetime()


        # rounding ends up in future
        if t_now <= t_now_rounded:
            t_now_rounded = t_now_rounded - datetime.timedelta(hours = 12) 

        latest_run = t_now_rounded.strftime('%Y-%m-%dT%H:%M:%SZ')
        logging.debug('latest run: {}'.format(latest_run))

        return latest_run

    def _latest_confirmed_run(self,station):
        # get base_time for each epsgram, only if all are available move to most recent
        base_time = set()
        for eps_type in ALL_EPSGRAM[0]:
            try:
                data = self._get_API_data_for_epsgram_v2(station,'2025-02-01T00:00:00Z',eps_type,raise_on_error=False)
                base_time.add(self._extract_available_base_time(data['error']))
            except ValueError as e:
                logging.warning('Error for {} at {}: {}'.format(station.name,eps_type,e))
                base_time.add(self._first_guess_base_time()) 

            
        # if there are multiple base_time, take the oldest
        if len(base_time)> 1:
            return min(base_time)
        else:
            return base_time.pop()


    @retry.retry(tries=5, delay=1)
    def _get_API_data_for_epsgram_v2(self,station,base_time,eps_type,raise_on_error=True):
        get = '{}products/opencharts_meteogram/?epsgram={}&base_time={}&station_name={}&lat={}&lon={}'.format(self._API_URL,
                                                                                            eps_type,
                                                                                            base_time,
                                                                                            station.name,
                                                                                            station.lat,
                                                                                            station.lon, raise_on_error=True)

        result = requests.get(get)

        if not result.ok and raise_on_error:
            logging.warning('Forecast not available for {} at {}'.format(station.name,base_time))
            raise ValueError('Forecast not available for {} at {}'.format(station.name,base_time))
        else:
            if result.status_code == 403:
                logging.warning('403 Forbidden for {} at {}'.format(station.name,base_time))
                raise ValueError('403 Forbidden for {} at {}'.format(station.name,base_time))
            else:
                try:
                    return result.json()
                except json.decoder.JSONDecodeError:
                    logging.warning('JSONDecodeError for {} at {}'.format(station.name,base_time))
                    raise ValueError('JSONDecodeError for {} at {}'.format(station.name,base_time))

    def _get_API_data_for_epsgram_no_error_catch(self,station,base_time,product,eps_type):
        get = '{}products/{}/?epsgram={}&base_time={}&station_name={}&lat={}&lon={}'.format(self._API_URL,
                                                                                            product,
                                                                                            eps_type,
                                                                                            base_time,
                                                                                            station.name,
                                                                                            station.lat,
                                                                                            station.lon)
        result = requests.get(get)
        return result.json()
    def _get_API_data_for_epsgram(self,station,base_time,product,eps_type):

        get = '{}products/{}/?epsgram={}&base_time={}&station_name={}&lat={}&lon={}'.format(self._API_URL,
                                                                                            product,
                                                                                            eps_type,
                                                                                            base_time,
                                                                                            station.name,
                                                                                            station.lat,
                                                                                            station.lon)
        result = requests.get(get)

        if not result.ok:
            logging.debug('Forecast not available for {} at {}'.format(station.name,base_time))
            raise ValueError('Forecast not available for {} at {}'.format(station.name,base_time))
        return result.json()

        
    def _request_epsgram_link_for_station(self,station, eps_type):
        data = self._get_API_data_for_epsgram_v2(station,station.base_time,eps_type)
        return data["data"]["link"]["href"]

    def _save_image_of_station(self,image_api,station,eps_type):
        image = requests.get(image_api)
        file = "./{}_{}.png".format(station.name,eps_type)
        with open(file, "wb") as img:
            img.write(image.content)
        logging.info("image saved in {}".format(file))
        return file

    def download_plots(self,requested_stations):
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

                    # update base_time with latest confirmed run
                    # base_time needs update before fetch
                    # if not updated, bot sends endless plots to users
                    base_time = self._latest_confirmed_run(Station)
                    logging.debug('base_time for {} updated to {}'.format(Station.name,base_time))
                    Station.base_time = base_time

                    self._download_plots(Station)


        # copy because we reset _plots_for_broadcast now
        plots_for_broadcast = self._plots_for_broadcast.copy()
        self._plots_for_broadcast = {}

        return plots_for_broadcast


    def _download_plots(self,Station):
            logging.info('Fetch plots for {}'.format(Station.name))
            plots = []
            for type in self._epsgrams:
                image_api =  self._request_epsgram_link_for_station(Station,type)
                plots.append(self._save_image_of_station(image_api,Station,type))
            self._plots_for_broadcast[Station.name] = plots

    def _new_forecast_available(self,Station):
            return Station.base_time != self._latest_confirmed_run(Station)
