import logging
import argparse
import time


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

    bot = PlotBot(args.bot_token)

    ecmwf = EcmwfApi()

    logging.info('Enter infinite loop')

    while True:

        bot.broadcast(ecmwf.download_latest_plots())

        snooze = 120
        logging.debug(f'snooze {snooze}s ...')
        time.sleep(snooze)

if __name__ == '__main__':
    main()
