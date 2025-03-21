import logging
import argparse
import time
import yaml
import sys

from ecmwf import EcmwfApi
from bot import PlotBot


def stop(bot):
    bot.stop()
    sys.exit(1)


<<<<<<< HEAD
def start_bot(bot, token, station_config, backup, admin_id, restart=False):
=======
def start_bot(bot, token, station_config, backup,admin_id, restart=False):
>>>>>>> eb10b87609dc0e830ceb6c049c755f73097bd762
    if restart:
        bot.stop()
    bot = PlotBot(token, station_config, backup, admin_id)
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

    # Enable logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=args.log_level,
    )

    logger = logging.getLogger(__name__)

    with open('stations.yaml', 'r') as file:
        station_config = yaml.safe_load(file)

<<<<<<< HEAD
    bot = start_bot(None,
                    args.bot_token,
                    station_config,
                    args.bot_backup,
                    args.admin_id,
                    restart=False)
=======
    bot = start_bot(None,args.bot_token, station_config, args.bot_backup, args.admin_id, restart=False)
>>>>>>> eb10b87609dc0e830ceb6c049c755f73097bd762

    ecmwf = EcmwfApi(station_config)
    ecmwf.override_base_time_from_init()

    logging.info('Enter infinite loop')

    while True:

        try:
            if bot.has_new_subscribers_waiting():
                bot.send_plots_to_new_subscribers(
                    ecmwf.download_plots(bot.stations_of_new_subscribers()))
            if bot.has_one_time_forecast_waiting():
                bot.send_one_time_forecast(
                    ecmwf.download_plots(bot.stations_of_one_time_request()))
            bot.broadcast(ecmwf.download_latest_plots())
            ecmwf.upgrade_basetime()
        except Exception as e:
            logging.error(f'An error occured: {e}')
            logging.error('Restart required')
            stop(bot)

        if bot.restart_required():
<<<<<<< HEAD
            bot = start_bot(bot,
                            args.bot_token,
                            station_config,
                            args.bot_backup,
                            args.admin_id,
                            restart=True)
=======
            bot = start_bot(bot, args.bot_token, station_config,
                              args.bot_backup, args.admin_id, restart=True)
>>>>>>> eb10b87609dc0e830ceb6c049c755f73097bd762
            logging.info('Bot restarted')

        snooze = 5
        logging.debug(f'snooze {snooze}s ...')
        time.sleep(snooze)


if __name__ == '__main__':
    main()
