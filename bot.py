import os

from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    Updater,
    PicklePersistence,
    CallbackContext,
)

from logger_config import logger

STATION_SELECT_ONE_TIME, STATION_SELECT_SUBSCRIBE, ONE_TIME, SUBSCRIBE, UNSUBSCRIBE = range(
    5)
TIMEOUT = 60


class PlotBot:

    def __init__(self, token, station_config, backup, db=None, admin_id=None):

        self._db = db
        # Create the Updater and pass it your bot's token.
        persistence = PicklePersistence(
            filename=os.path.join(backup, 'bot.pkl'))
        self._station_names = [station["name"] for station in station_config]
        self._region_of_stations = {
            station["name"]: station["region"]
            for station in station_config
        }
        self._station_regions = {
            station["region"]
            for station in station_config
        }
        self._subscriptions = {
            station: set()
            for station in self._station_names
        }
        self._one_time_forecast_requests = {
            station: set()
            for station in self._station_names
        }
        # filter for stations
        self._filter_stations = Filters.regex("^(" +
                                              "|".join(self._station_names) +
                                              ")$")
        # filter for regions
        self._filter_regions = Filters.regex("^(" +
                                             "|".join(self._station_regions) +
                                             ")$")
        # filter for all commands of bot
        self._filter_all_commands = Filters.regex(
            "^(/locations|/subscribe|/unsubscribe|/plots|/help|/cancel|/start)$"
        )

        # filter for meaningful messages that are explicitly handled by the bot
        # inverse of all filters above
        self._filter_meaningful_messages = ~self._filter_all_commands & ~self._filter_regions & ~self._filter_stations

        self.updater = Updater(token, persistence=persistence)
        self._dp = self.updater.dispatcher
        # initialize bot_data with empty set for each station if not present
        [
            self._dp.bot_data.setdefault(station, set())
            for station in self._station_names
        ]
        self._stop = False
        self._admin_id = admin_id

        self._dp.add_handler(CommandHandler('start', self._help))
        self._dp.add_handler(CommandHandler('help', self._help))
        self._dp.add_handler(CommandHandler('cancel', self._cancel))
        self._dp.add_handler(
            CommandHandler('locations', self._overview_locations))

        # add help handler for all other messages
        self._dp.add_handler(
            MessageHandler(self._filter_meaningful_messages, self._help))

        subscription_handler = ConversationHandler(
            entry_points=[
                CommandHandler('subscribe', self._choose_all_region)
            ],
            states={
                STATION_SELECT_SUBSCRIBE:
                [MessageHandler(self._filter_regions, self._choose_station)],
                SUBSCRIBE: [
                    MessageHandler(self._filter_stations,
                                   self._subscribe_for_station)
                ],
            },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            conversation_timeout=TIMEOUT,
        )

        one_time_forecast_handler = ConversationHandler(
            entry_points=[CommandHandler('plots', self._choose_all_region)],
            states={
                STATION_SELECT_ONE_TIME: [
                    MessageHandler(self._filter_regions,
                                   self._choose_all_station)
                ],
                ONE_TIME: [
                    MessageHandler(self._filter_stations,
                                   self._request_one_time_forecast_for_station)
                ],
            },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            conversation_timeout=TIMEOUT,
        )

        unsubscription_handler = ConversationHandler(
            entry_points=[CommandHandler('unsubscribe', self._revoke_station)],
            states={
                UNSUBSCRIBE: [
                    MessageHandler(self._filter_stations,
                                   self._unsubscribe_for_station)
                ],
            },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            conversation_timeout=TIMEOUT,
        )

        self._dp.add_handler(subscription_handler)
        self._dp.add_handler(unsubscription_handler)
        self._dp.add_handler(one_time_forecast_handler)
        self._dp.add_error_handler(self._error)

        logger.info(self._collect_bot_data(short=True))

    def connect(self):
        self.updater.start_polling()

    def _error(self, update: Update, context: CallbackContext):
        self._stop = True

    def restart_required(self):
        return self._stop

    def stop(self):
        self.updater.stop()
        self._dp.stop()

    def _overview_locations(self, update: Update, context: CallbackContext):
        update.message.reply_markdown("\n".join(self._available_locations()))

    def _available_locations(self):
        text = ["_Available locations_"]
        for location in sorted(self._station_regions):
            text.append(f'')
            text.append(f'*{location}*')
            text.extend([
                f'- {n}' for n in self._get_station_names_for_region(location)
            ])
        return text

    def _help(self, update: Update, context: CallbackContext):

        greetings = "Hi! I am OpenEns. I supply you with ECWMF meteograms for places in Switzerland. \
                    \nTwice a day a new set of meteograms is available, usually at *8:00* for the *00 UTC* run and at *20:00* for the *12 UTC* run. \
                    \nYou can subscribe for a location or request a forecast only once. \
                    \n\n*Commands* \
                    \n- To get a list of available locations type /locations. \
                    \n- To subscribe type /subscribe. \
                    \n- To request a forecast type /plots. \
                    \n- To unsubscribe type /unsubscribe. \
                    \n- To get this message type /help. \
                    \n- To cancel any operation type /cancel. \
                    \n\nAll available commands are also shown in the menu at the bottom of the chat. \
                    \n\nIf you have any questions, feedback, or if the bot missed a place you want forecasts for, please open an issue on GitHub: \
                    \nhttps://github.com/jonasjucker/ensplotbot \
                    \n\n*Have fun!*"

        update.message.reply_markdown(greetings)

    def _get_subscriptions_of_user(self, user_id, context) -> list[str]:
        return [
            station for station, users in context.bot_data.items()
            if user_id in users
        ]

    def _choose_station(self, update: Update, context: CallbackContext) -> int:
        region = update.message.text
        station_of_region = self._get_station_names_for_region(region)

        user_id = update.message.chat_id

        # Get the stations that the user has already subscribed to
        subscribed_stations = self._get_subscriptions_of_user(user_id, context)

        # Only include stations that the user has not already subscribed to
        not_subscribed_for_all_stations = self._send_station_keyboard(
            update, [
                name for name in station_of_region
                if name not in subscribed_stations
            ])

        return SUBSCRIBE if not_subscribed_for_all_stations else ConversationHandler.END

    def _choose_all_region(self, update: Update,
                           context: CallbackContext) -> int:

        entry_point = update.message.text

        self._send_region_keyboard(update,
                                   [name for name in self._station_regions])

        # check that entry point is valid
        if entry_point == '/subscribe':
            return STATION_SELECT_SUBSCRIBE
        elif entry_point == '/plots':
            return STATION_SELECT_ONE_TIME
        else:
            raise ValueError(f'Invalid entry point: {entry_point}')

    def _get_station_names_for_region(self, region) -> list[str]:
        return [
            name for name in sorted(self._station_names)
            if self._region_of_stations[name] == region
        ]

    def _choose_all_station(self, update: Update,
                            context: CallbackContext) -> int:
        region = update.message.text

        self._send_station_keyboard(update,
                                    self._get_station_names_for_region(region))

        return ONE_TIME

    def _revoke_station(self, update: Update, context: CallbackContext) -> int:
        user_id = update.message.chat_id

        # Get the stations that the user has already subscribed to
        subscribed_stations = self._get_subscriptions_of_user(user_id, context)

        # Only include stations that the user has already subscribed to
        subscription_present = self._send_station_keyboard(
            update, [
                name
                for name in self._station_names if name in subscribed_stations
            ])

        return UNSUBSCRIBE if subscription_present else ConversationHandler.END

    def _send_region_keyboard(self, update: Update, region_names: list[str]):
        return self._send_keyboard(update, region_names, 'region')

    def _send_keyboard(self, update: Update, names: list[str], type: str):
        reply_keyboard = [[name] for name in names]

        if reply_keyboard:
            reply_text = f'Choose a {type}'
            update.message.reply_text(
                reply_text,
                reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                 one_time_keyboard=True),
            )
            return True
        else:
            update.message.reply_text(f"Sorry, no more {type}s for you here",
                                      reply_markup=ReplyKeyboardRemove())
            return False

    def _send_station_keyboard(self, update: Update, station_names: list[str]):
        return self._send_keyboard(update, station_names, 'station')

    def _unsubscribe_for_station(self, update: Update,
                                 context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        reply_text = f'Unubscribed for Station {msg_text}'
        update.message.reply_text(
            reply_text,
            reply_markup=ReplyKeyboardRemove(),
        )
        self._revoke_subscription(user.id, msg_text, context.bot_data)
        logger.info(f' {user.first_name} unsubscribed for Station {msg_text}')

        return ConversationHandler.END

    def _log_stats_and_send_to_admin(self):
        stats = self._collect_bot_data()
        logger.info(stats)
        if self._admin_id:
            self._dp.bot.send_message(chat_id=self._admin_id, text=stats)

    def _subscribe_for_station(self, update: Update,
                               context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        reply_text = f"You sucessfully subscribed for {msg_text}. You will receive your first plots in a minute or two..."
        update.message.reply_text(
            reply_text,
            reply_markup=ReplyKeyboardRemove(),
        )
        self._register_subscription(user.id, msg_text, context.bot_data)

        logger.info(f' {user.first_name} subscribed for Station {msg_text}')

        self._log_stats_and_send_to_admin()

        return ConversationHandler.END

    def _request_one_time_forecast_for_station(
            self, update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        reply_text = f"You sucessfully requested a forecast for {msg_text}. You will receive your first plots in a minute or two..."
        update.message.reply_text(
            reply_text,
            reply_markup=ReplyKeyboardRemove(),
        )
        self._one_time_forecast_requests[msg_text].add(user.id)

        logger.info(
            f' {user.first_name} requested forecast for Station {msg_text}')

        return ConversationHandler.END

    def _register_subscription(self, id, station, bot_data):

        # add user to subscription list for given station
        bot_data[station].add(id)

        self._subscriptions[station].add(id)

    def _revoke_subscription(self, id, station, bot_data):

        # remove user to subscription list for given station
        if id in bot_data[station]:
            bot_data[station].remove(id)

    def _unsubscribe(self, update: Update, context: CallbackContext):
        reply_text = "You sucessfully unsubscribed."
        update.message.reply_text(reply_text)

        # remove user from subscription list
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_id',
                                    set())  # create key if not present
        if user_id in context.bot_data['user_id']:
            context.bot_data['user_id'].remove(user_id)

    def _cancel(self, update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        logger.info("User %s canceled the conversation.", user.first_name)
        update.message.reply_text('Bye! I hope we can talk again some day.',
                                  reply_markup=ReplyKeyboardRemove())

        return ConversationHandler.END

    def has_new_subscribers_waiting(self):
        return any(users for users in self._subscriptions.values())

    def has_one_time_forecast_waiting(self):
        return any(users
                   for users in self._one_time_forecast_requests.values())

    def stations_of_one_time_request(self):
        return [
            station
            for station, users in self._one_time_forecast_requests.items()
            if users
        ]

    def stations_of_new_subscribers(self):
        return [
            station for station, users in self._subscriptions.items() if users
        ]

    def _send_plot_to_user(self, plots, station_name, user_id):
        logger.debug(f'Send plot to user: {user_id}')
        try:
            self._dp.bot.send_message(chat_id=user_id, text=station_name)
            for plot in plots[station_name]:
                self._dp.bot.send_photo(chat_id=user_id,
                                        photo=open(plot, 'rb'))
        except:
            logger.warning(f'Could not send plot to user: {user_id}')
            if self._db:
                self._db.log_activity(
                    activity_type="fail-send-plot",
                    user_id=user_id,
                    station=station_name,
                )

    def _send_plots(self, plots, requests):
        for station_name, users in requests.items():
            for user_id in users:
                self._send_plot_to_user(plots, station_name, user_id)

    def send_plots_to_new_subscribers(self, plots):
        self._send_plots(plots, self._subscriptions)
        logger.info('plots sent to new subscribers')

        if self._db:
            for station, users in self._subscriptions.items():
                for user_id in users:
                    self._db.log_activity(
                        activity_type="subscription",
                        user_id=user_id,
                        station=station,
                    )

        self._subscriptions = {
            station: set()
            for station in self._station_names
        }

    def send_one_time_forecast(self, plots):
        self._send_plots(plots, self._one_time_forecast_requests)
        logger.info('plots sent to one time forecast requests')

        if self._db:
            for station, users in self._one_time_forecast_requests.items():
                for user_id in users:
                    self._db.log_activity(
                        activity_type="one-time-request",
                        user_id=user_id,
                        station=station,
                    )

        self._one_time_forecast_requests = {
            station: set()
            for station in self._station_names
        }

    def _collect_bot_data(self, short=False):
        stats = []
        stats.append('')
        for station, users in self._dp.bot_data.items():
            if not short:
                stats.append(f'{station}: {len(users)}')
        unique_users = set()
        for users in self._dp.bot_data.values():
            unique_users.update(users)
        stats.append(f'Total subscribers: {len(unique_users)}')
        stats_str = "\n".join(stats)
        return stats_str

    def stations_with_subscribers(self):
        return sorted(
            [station for station, users in self._dp.bot_data.items() if users])

    def broadcast(self, plots):
        if plots:
            for station_name in plots:
                for user_id in self._dp.bot_data.get(station_name, set()):
                    self._send_plot_to_user(plots, station_name, user_id)
            logger.info('plots sent to all users')
