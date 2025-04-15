import logging
import argparse
import time
import yaml
import sys
import threading
import asyncio

from ecmwf import EcmwfApi
from bot import PlotBot
from logger_config import logger
from db import Database


async def await_func(func, *args):
    async_func = asyncio.create_task(func(*args))
    await async_func


def run_asyncio(func, *args):
    asyncio.run(await_func(func, *args))


def run_asyncio_in_thread(func, name, *args):
    thread = threading.Thread(target=run_asyncio,
                              name=name,
                              daemon=True,
                              args=[func, *args])
    thread.start()
    logging.debug(f'Started thread: {name}')


def start_bot(token, station_config, admin_id, db):
    bot = PlotBot(token, station_config, admin_id, db)
    run_asyncio_in_thread(bot.connect, 'bot-connect')
    return bot


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

    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.setLevel(args.log_level)

    with open('stations.yaml', 'r') as file:
        station_config = yaml.safe_load(file)

    db = Database('config.yml')

    bot = start_bot(args.bot_token, station_config, args.admin_id, db)

    ecmwf = EcmwfApi(station_config)
    ecmwf.override_base_time_from_init()

    logger.info('Enter infinite loop')

    while True:

        try:
            ecmwf.upgrade_basetime_global()
            ecmwf.upgrade_basetime_stations()
            if bot.has_new_subscribers_waiting():
                run_asyncio_in_thread(
                    bot.send_plots_to_new_subscribers, 'new-subscribers',
                    ecmwf.download_plots(bot.stations_of_new_subscribers()))
            if bot.has_one_time_forecast_waiting():
                run_asyncio_in_thread(
                    bot.send_one_time_forecast, 'one-time-forecast',
                    ecmwf.download_plots(bot.stations_of_one_time_request()))
            run_asyncio_in_thread(
                bot.broadcast, 'broadcast',
                ecmwf.download_latest_plots(db.stations_with_subscribers()))
            ecmwf.cache_plots()
        except Exception as e:
            logger.error(f'An error occured: {e}')
            sys.exit(1)

        # each day at 00:00 UTC
        if time.strftime('%H:%M') == '00:00':
            logger.info(db.get_activity_summary())
            time.sleep(60)  # wait for the next minute to avoid double logging
        snooze = 5
        logger.debug(f'snooze {snooze}s ...')
        time.sleep(snooze)


if __name__ == '__main__':
    main()
