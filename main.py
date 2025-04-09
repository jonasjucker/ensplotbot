import logging
import argparse
import time
import yaml
import sys

from ecmwf import EcmwfApi
from bot import PlotBot
from logger_config import logger
from db import Database


def stop(bot):
    bot.stop()
    sys.exit(1)


def start_bot(bot, token, station_config, backup, admin_id, db, restart=False):
    if restart:
        bot.stop()
    bot = PlotBot(token, station_config, backup, admin_id=admin_id, db=db)
    bot.connect()
    return bot


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument('--bot_token', \
                        dest='bot_token', \
                        type=str, \
                        help='unique token of bot (KEEP PRIVATE!)')
    parser.add_argument('--bot_backup',
                        dest='bot_backup', \
                        type=str, \
                        default='backup',
                        help='Backup folder for the bot')

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

    db = Database('config.yml')

    bot = start_bot(None,
                    args.bot_token,
                    station_config,
                    args.bot_backup,
                    args.admin_id,
                    db=db,
                    restart=False)

    ecmwf = EcmwfApi(station_config)
    ecmwf.override_base_time_from_init()

    logger.info('Enter infinite loop')

    while True:

        try:
            ecmwf.upgrade_basetime_global()
            ecmwf.upgrade_basetime_stations()
            if bot.has_new_subscribers_waiting():
                bot.send_plots_to_new_subscribers(
                    ecmwf.download_plots(bot.stations_of_new_subscribers()))
            if bot.has_one_time_forecast_waiting():
                bot.send_one_time_forecast(
                    ecmwf.download_plots(bot.stations_of_one_time_request()))
            bot.broadcast(
                ecmwf.download_latest_plots(bot.stations_with_subscribers()))
            ecmwf.cache_plots()
        except Exception as e:
            logger.error(f'An error occured: {e}')
            logger.error('Restart required')
            stop(bot)

        if bot.restart_required():
            bot = start_bot(bot,
                            args.bot_token,
                            station_config,
                            args.bot_backup,
                            args.admin_id,
                            db=db,
                            restart=True)
            logger.info('Bot restarted')

        # each day at 00:00 UTC
        if time.strftime('%H:%M') == '00:00':
            db.get_activity_summary()
        snooze = 5
        logger.debug(f'snooze {snooze}s ...')
        time.sleep(snooze)


if __name__ == '__main__':
    main()
