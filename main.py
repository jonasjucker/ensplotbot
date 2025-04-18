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

    config_file = 'config.yml'

    db = Database(config_file)

    bot = PlotBot(config_file, station_config, db=db, ecmwf=ecmwf)
    bot.start()

    # we only end up here if the bot had an error
    sys.exit(1)


if __name__ == '__main__':
    main()
