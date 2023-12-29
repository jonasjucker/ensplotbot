import logging
import argparse
import time
import yaml


from ecmwf import EcmwfApi
from bot import PlotBot

def main():

    # Enable logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
        level=logging.INFO,
    )

    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser()

    parser.add_argument('--bot_token', \
                        dest='bot_token', \
                        type=str, \
                        help='unique token of bot (KEEP PRIVATE!)')

    args = parser.parse_args()
    
    with open('stations.yaml', 'r') as file:
        station_config = yaml.safe_load(file)


    bot = PlotBot(args.bot_token,station_config)

    ecmwf = EcmwfApi(station_config)

    logging.info('Enter infinite loop')

    while True:

        try:
            if bot.has_new_subscribers_waiting():
                bot.send_plots_to_new_subscribers(ecmwf.download_plots())
            bot.broadcast(ecmwf.download_latest_plots())
        except:
            pass

        snooze = 120
        logging.debug(f'snooze {snooze}s ...')
        time.sleep(snooze)

if __name__ == '__main__':
    main()
