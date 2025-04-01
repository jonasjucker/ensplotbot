from constants import ALL_EPSGRAM


class APILocation():

    def __init__(self, name, lat, lon, region, api_name=None):
        self.name = name
        self.api_name = name if api_name is None else api_name
        self.lat = lat
        self.lon = lon
        self.region = region
        self.base_time = None
        # set to true, otherwise bot sends plots to users after startup
        self.has_been_broadcasted = True
        self.plots_cached = False
        self.all_plots = [f'./{name}_{i}.png' for i in ALL_EPSGRAM]

    def upgrade_basetime(self, basetime):
        self.base_time = basetime
        self.has_been_broadcasted = False
        self.plots_cached = False
