import requests
import json
import datetime
import logging

import pandas as pd

d10_plume = 'classical_plume'
d10_eps = 'classical_10d'
d15_eps = 'classical_15d'
#d15_eps_with_climate='classical_15d_with_climate'

class Station():
    def __init__(self,name,lat,lon):
        self.name = name
        self.lat = lat
        self.lon = lon
        self.base_time = None

TST = Station(name='Tschiertschen',lat='46.8167',lon='9.6')
ALL_STATIONS = [TST]
#ALL_EPSGRAM = [d10_plume,d10_eps,d15_eps,d15_eps_with_climate] 
ALL_EPSGRAM = [d10_plume,d10_eps,d15_eps] 

class EcmwfApi():

    def __init__(self):
        self._API_URL = "https://charts.ecmwf.int/opencharts-api/v1/" 
        self._stations = ALL_STATIONS
        self._epsgrams = ALL_EPSGRAM

        # populate stations with valid run
        for Station in self._stations:
            Station.base_time = self._latest_confirmed_run(Station)


    def _latest_run(self):
        t_now = datetime.datetime.now()
        t_now_rounded = pd.Timestamp.now().round(freq='12H').to_pydatetime()

        # rounding ends up in future
        if t_now <= t_now_rounded:
            t_now_rounded = t_now_rounded - datetime.timedelta(hours = 12) 
        return t_now_rounded.strftime('%Y-%m-%dT%H:%M:%SZ')


    def _latest_confirmed_run(self,station):
        '''
        Function only works if not called between a transition
        from 23:59 (last valid run 12:00) and 00:01 (last valid run 00:00).
        latest_run() then returns two different timestamps what is bad!
        '''

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

    def download_latest_plots(self):
        plots = []
        for Station in self._stations:
            if self._new_forecast_available(Station):
                plots.extend(self._download_plots(Station))

        return plots


    def _download_plots(self,Station):
            logging.info('Fetch plots for {}'.format(Station.name))
            plots = []
            for type in self._epsgrams:
                image_api =  self._request_epsgram_link_for_station(Station,type)
                plots.append(self._save_image_of_station(image_api,Station,type))

            return plots

    def _new_forecast_available(self,Station):
            return Station.base_time != self._latest_confirmed_run(Station)
