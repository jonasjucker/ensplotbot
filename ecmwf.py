import requests
import json
import datetime
import time
import logging

import pandas as pd

d10_plume = 'classical_plume'
d10_eps = 'classical_10d'
d15_eps = 'classical_15d'

class Station():
    def __init__(self,name,lat,lon):
        self.name = name
        self.lat = lat
        self.lon = lon
        self.base_time = None

TST = Station(name='Tschiertschen',lat='46.8167',lon='9.6')
DVS = Station(name='Davos',lat='46.8043',lon='9.83723')
ELM = Station(name='Elm',lat='46.9167',lon='9.16667')
ALL_STATIONS = [TST,DVS]
ALL_EPSGRAM = [d10_plume,d10_eps,d15_eps] 

class EcmwfApi():

    def __init__(self):
        self._API_URL = "https://charts.ecmwf.int/opencharts-api/v1/" 
        self._stations = ALL_STATIONS
        self._epsgrams = ALL_EPSGRAM

        self._plots_for_broadcast = {}

        # populate stations with valid run
        for Station in self._stations:
            Station.base_time = self._latest_confirmed_run(Station)
            logging.debug('init station {} with base_time {}'.format(Station.name,Station.base_time))


    def _is_dangerous_time(self):
        # time is dangerous around 11:59 - 12:01  and 23:59 - 00:01
        return ( (datetime.time(11, 59, 0) < datetime.datetime.now().time() < datetime.time(12,1,0)) or \
                (datetime.time(23, 59, 0) < datetime.datetime.now().time() < datetime.time(0,1,0)) )

    def _latest_run(self):
        t_now = datetime.datetime.now()
        t_now_rounded = pd.Timestamp.now().round(freq='12H').to_pydatetime()


        while (self._is_dangerous_time()):
            time.sleep(10)
            logging.info('snooze 10s because time close to noon/midnight: {}'.format(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')))

        # rounding ends up in future
        if t_now <= t_now_rounded:
            t_now_rounded = t_now_rounded - datetime.timedelta(hours = 12) 
        return t_now_rounded.strftime('%Y-%m-%dT%H:%M:%SZ')


    def _latest_confirmed_run(self,station):

        eps_type = 'classical_plume'
        product = 'opencharts_meteogram'

        data = self._get_API_data_for_epsgram(station,self._latest_run(),product,eps_type)

        # API cannot provide link for non-existing plot
        try:
            data["data"]["link"]["href"]
            return self._latest_run()
        except KeyError:
            latest_run_time_object = datetime.datetime.strptime(self._latest_run(),'%Y-%m-%dT%H:%M:%SZ') - datetime.timedelta(hours = 12)
            return latest_run_time_object.strftime('%Y-%m-%dT%H:%M:%SZ')



    def _get_API_data_for_epsgram(self,station,base_time,product,eps_type):

        get = '{}products/{}/?epsgram={}&base_time={}&station_name={}&lat={}&lon={}'.format(self._API_URL,
                                                                                            product,
                                                                                            eps_type,
                                                                                            base_time,
                                                                                            station.name,
                                                                                            station.lat,
                                                                                            station.lon)
        result = requests.get(get)
        return result.json()

        
    def _request_epsgram_link_for_station(self,station, eps_type):
        product = 'opencharts_meteogram'

        data = self._get_API_data_for_epsgram(station,station.base_time,product,eps_type)
        return data["data"]["link"]["href"]

    def _save_image_of_station(self,image_api,station,eps_type):
        image = requests.get(image_api)
        file = "./{}_{}.png".format(station.name,eps_type)
        with open(file, "wb") as img:
            img.write(image.content)
        logging.info("image saved in {}".format(file))
        return file

    def download_plots(self):
        for Station in self._stations:
            self._download_plots(Station)

        # copy because we reset _plots_for_broadcast now
        plots_for_broadcast = self._plots_for_broadcast.copy()
        self._plots_for_broadcast = {}

        return plots_for_broadcast

    def download_latest_plots(self):
        if not self._is_dangerous_time():
            for Station in self._stations:
                    if self._new_forecast_available(Station):

                        # update base_time with latest confirmed run
                        # base_time needs update before fetch
                        # if not updated, bot sends endless plots to users
                        Station.base_time = self._latest_confirmed_run(Station)

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
