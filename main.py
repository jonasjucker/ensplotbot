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
    logging.info(f'Started thread: {name}')


def start_bot(bot, token, station_config, backup, admin_id):
    bot = PlotBot(token, station_config, backup, admin_id)
    run_asyncio_in_thread(bot.connect, 'bot-connect')
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

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.scheduler").setLevel(logging.DEBUG)
    logging.getLogger("telegram.ext.Application").setLevel(logging.DEBUG)

    logger.setLevel(args.log_level)

    with open('stations.yaml', 'r') as file:
        station_config = yaml.safe_load(file)

    bot = start_bot(None, args.bot_token, station_config, args.bot_backup,
                    args.admin_id)

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
                ecmwf.download_latest_plots(bot.stations_with_subscribers()))
            ecmwf.cache_plots()
        except Exception as e:
            logger.error(f'An error occured: {e}')
            logger.error('Restart required')
            sys.exit(1)

        if bot.restart_required():
            bot = start_bot(bot, args.bot_token, station_config,
                            args.bot_backup, args.admin_id)
            logger.info('Bot restarted')

        snooze = 5
        logger.debug(f'snooze {snooze}s ...')
        time.sleep(snooze)


if __name__ == '__main__':
    main()
