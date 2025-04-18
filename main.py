import logging
import argparse
import yaml
import sys

from ecmwf import EcmwfApi
from bot import PlotBot
from logger_config import logger
from db import Database


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument('--bot_token', \
                        dest='bot_token', \
                        type=str, \
                        help='unique token of bot (KEEP PRIVATE!)')

    parser.add_argument('--admin_id',
                        dest='admin_id', \
                        type=int, \
                        help='Telegram ID of the admin')

    parser.add_argument(
        '--log_level',
        dest='log_level',
        type=int,
        default=logging.INFO,
        choices=[logging.DEBUG, logging.INFO],
        help=
        f'set the logging level ({logging.DEBUG}: DEBUG, {logging.INFO}: INFO')

    args = parser.parse_args()

    logger.setLevel(args.log_level)

    with open('stations.yaml', 'r') as file:
        station_config = yaml.safe_load(file)

    ecmwf = EcmwfApi(station_config)

    db = Database('config.yml')

    bot = PlotBot(args.bot_token,
                  station_config,
                  admin_id=args.admin_id,
                  db=db,
                  ecmwf=ecmwf)
    bot.start()

    # we should not be here
    sys.exit(1)


if __name__ == '__main__':
    main()
