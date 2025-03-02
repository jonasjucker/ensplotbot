import logging
import socket
import time

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

CHOOSE, STATION = range(2)

class PlotBot:

    def __init__(self,token,station_config):

        # Create the Updater and pass it your bot's token.
        persistence = PicklePersistence(filename='backup/bot.pkl')
        self._station_names = [station["name"] for station in station_config]
        self._subscriptions = {station:set() for station in self._station_names}
        self._one_time_forecast_requests = {station:set() for station in self._station_names}
        self._filter_stations = Filters.regex("^(" + "|".join(self._station_names) + ")$")
        self.updater = Updater(token, persistence=persistence)
        self._dp = self.updater.dispatcher

        self._dp.add_handler(CommandHandler('start',self._start))


        subscription_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.regex('^(subscribe)$'), self._choose_station)],
            states={
                STATION: [MessageHandler(self._filter_stations, self._subscribe_for_station)],
                },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            )

        one_time_forecast_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.regex('^(one-time-forecast)$'), self._choose_all_station)],
            states={
                STATION: [MessageHandler(self._filter_stations, self._request_one_time_forecast_for_station)],
                },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            )

        unsubscription_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.regex('^(unsubscribe)$'), self._revoke_station)],
            states={
                STATION: [MessageHandler(self._filter_stations, self._unsubscribe_for_station)],
                },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            )

        self._dp.add_handler(subscription_handler)
        self._dp.add_handler(unsubscription_handler)
        self._dp.add_handler(one_time_forecast_handler)

        # start the bot
        self.updater.start_polling()


    def _start(self,update: Update, context: CallbackContext):
        reply_keyboard = [['subscribe'], ['unsubscribe'], ['one-time-forecast']]

        reply_text = "Hi! I am OpenEns. I supply you with the latest ECWMF meteograms. \
                      As soon as the latest forecast is available I deliver them to you. \
                      You can subscribe or get it as a one-time-forecast for multiple locations in the Alps."

        update.message.reply_text(reply_text,
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False),
        )
    
    def _choose_station(self, update: Update, context: CallbackContext) -> int:
        user_id = update.message.chat_id

        # Get the stations that the user has already subscribed to
        subscribed_stations = [station for station, users in context.bot_data.items() if user_id in users]

        # Only include stations that the user has not already subscribed to
        self._send_station_keyboard(update, [name for name in self._station_names if name not in subscribed_stations])

        return STATION

    def _choose_all_station(self, update: Update, context: CallbackContext) -> int:
        user_id = update.message.chat_id

        # Only include stations that the user has not already subscribed to
        self._send_station_keyboard(update, [name for name in self._station_names])

        return STATION

    def _revoke_station(self, update: Update, context: CallbackContext) -> int:
        user_id = update.message.chat_id

        # Get the stations that the user has already subscribed to
        subscribed_stations = [station for station, users in context.bot_data.items() if user_id in users]

        # Only include stations that the user has already subscribed to
        self._send_station_keyboard(update, [name for name in self._station_names if name in subscribed_stations])

        return STATION

    def _send_station_keyboard(self, update: Update, station_names: list[str]):
        reply_keyboard = [[name] for name in station_names]

        if reply_keyboard:
            reply_text = "Choose a station"
            update.message.reply_text(reply_text,
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
            )
        else:
            update.message.reply_text("Sorry, no more stations for you here",
                reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

    def _unsubscribe_for_station(self,update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        reply_text = f'Unubscribed for Station {msg_text}'
        update.message.reply_text(reply_text,
        reply_markup=ReplyKeyboardRemove(),
        )
        self._revoke_subscription(user,msg_text,context)
        logging.info(f' {user.first_name} unsubscribed for Station {msg_text}')

        return ConversationHandler.END

    def _subscribe_for_station(self,update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        reply_text = f"You sucessfully subscribed for {msg_text}. You will receive your first plots in a minute or two..."
        update.message.reply_text(reply_text,
            reply_markup=ReplyKeyboardRemove(),
            )
        self._register_subscription(user,msg_text,context)

        logging.info(f' {user.first_name} subscribed for Station {msg_text}')

        return ConversationHandler.END

    def _request_one_time_forecast_for_station(self,update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        reply_text = f"You sucessfully requested a forecast for {msg_text}. You will receive your first plots in a minute or two..."
        update.message.reply_text(reply_text,
            reply_markup=ReplyKeyboardRemove(),
            )
        self._one_time_forecast_requests[msg_text].add(user.id)

        logging.info(f' {user.first_name} requested forecast for Station {msg_text}')

        return ConversationHandler.END


    def _register_subscription(self,user,station,context):

        # add user to subscription list for given station
        context.bot_data.setdefault(station, set())
        context.bot_data[station].add(user.id)

        self._subscriptions[station].add(user.id)

        logging.debug(context.bot_data.setdefault(station, set()))

    def _revoke_subscription(self,user,station,context):

        # remove user to subscription list for given station
        if user.id in context.bot_data[station]:
            context.bot_data[station].remove(user.id)

        logging.debug(context.bot_data.setdefault(station, set()))


    def _unsubscribe(self,update: Update, context: CallbackContext):
        reply_text = "You sucessfully unsubscribed."
        update.message.reply_text(reply_text)

        # remove user from subscription list
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_id', set()) # create key if not present
        if user_id in context.bot_data['user_id']:
            context.bot_data['user_id'].remove(user_id)

        logging.debug(context.bot_data.setdefault('user_id', set()))

    def _cancel(self,update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        logging.info("User %s canceled the conversation.", user.first_name)
        update.message.reply_text(
            'Bye! I hope we can talk again some day.', reply_markup=ReplyKeyboardRemove()
        )

        return ConversationHandler.END

    def has_new_subscribers_waiting(self):
        return any(users for users in self._subscriptions.values())

    def has_one_time_forecast_waiting(self):
        return any(users for users in self._one_time_forecast_requests.values())

    def stations_of_one_time_request(self):
        return [station for station, users in self._one_time_forecast_requests.items() if users]

    def stations_of_new_subscribers(self):
        return [station for station, users in self._subscriptions.items() if users]

    def send_plots_to_new_subscribers(self, plots):
        for station_name, users in self._subscriptions.items():
            for user_id in users:
                self._dp.bot.send_message(chat_id=user_id, text=station_name)
                for plot in plots[station_name]:
                    self._dp.bot.send_photo(chat_id=user_id, photo=open(plot, 'rb'))
        logging.info('plots sent to new subscribers')

        self._subscriptions = {station: set() for station in self._station_names}

    def send_one_time_forecast(self, plots):
        for station_name, users in self._one_time_forecast_requests.items():
            for user_id in users:
                self._dp.bot.send_message(chat_id=user_id, text=station_name)
                for plot in plots[station_name]:
                    self._dp.bot.send_photo(chat_id=user_id, photo=open(plot, 'rb'))
        logging.info('plots sent to one time forecast requests')

        self._one_time_forecast_requests = {station: set() for station in self._station_names}

    def broadcast(self,plots):
        if plots:
            for station_name in plots:
                for user_id in self._dp.bot_data[station_name]:
                    logging.debug(user_id)
                    try:
                        self._dp.bot.send_message(chat_id=user_id, text=station_name)
                        for plot in plots[station_name]:
                            self._dp.bot.send_photo(chat_id=user_id, photo=open(plot, 'rb'))
                    except:
                        logging.info(f'Could not send message to user: {user_id}')

            logging.info('plots sent to all users')
