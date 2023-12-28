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

        unsubscription_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.regex('^(unsubscribe)$'), self._choose_station)],
            states={
                STATION: [MessageHandler(self._filter_stations, self._unsubscribe_for_station)],
                },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            )

        self._dp.add_handler(subscription_handler)
        self._dp.add_handler(unsubscription_handler)

        # start the bot
        self.updater.start_polling()

        self._new_users_waiting_for_plots = []


    def _start(self,update: Update, context: CallbackContext):
        reply_keyboard = [['subscribe', 'unsubscribe']]

        reply_text = "Hi! I am OpenEns. I supply you with the latest ECWMF meteograms. \
                      As soon as the latest forecast is available I deliver them to you. \
                      You can subscribe for multiple locations in the Alps."

        update.message.reply_text(reply_text,
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False),
        )

    def _choose_station(self,update: Update, context: CallbackContext) -> int:
        reply_keyboard = [[name] for name in self._station_names]

        reply_text = "Choose a station"
        update.message.reply_text(reply_text,
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
        )

        return STATION

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

        self._new_users_waiting_for_plots.append(user.id)

        logging.info(f' {user.first_name} subscribed for Station {msg_text}')

        return ConversationHandler.END

    def _register_subscription(self,user,station,context):

        # add user to subscription list for given station
        context.bot_data.setdefault(station, set())
        context.bot_data[station].add(user.id)

        logging.info(context.bot_data.setdefault(station, set()))

    def _revoke_subscription(self,user,station,context):

        # remove user to subscription list for given station
        if user.id in context.bot_data[station]:
            context.bot_data[station].remove(user.id)

        logging.info(context.bot_data.setdefault(station, set()))


    def _unsubscribe(self,update: Update, context: CallbackContext):
        reply_text = "You sucessfully unsubscribed."
        update.message.reply_text(reply_text)

        # remove user from subscription list
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_id', set()) # create key if not present
        if user_id in context.bot_data['user_id']:
            context.bot_data['user_id'].remove(user_id)

        logging.info(context.bot_data.setdefault('user_id', set()))

    def _cancel(self,update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        logging.info("User %s canceled the conversation.", user.first_name)
        update.message.reply_text(
            'Bye! I hope we can talk again some day.', reply_markup=ReplyKeyboardRemove()
        )

        return ConversationHandler.END

    def has_new_subscribers_waiting(self):
        if self._new_users_waiting_for_plots:
            return True
        else:
            return False

    def send_plots_to_new_subscribers(self,plots):
        for user_id in self._new_users_waiting_for_plots:
            for station_name in plots:
                if user_id in self._dp.bot_data[station_name]:
                    self._dp.bot.send_message(chat_id=user_id, text=station_name)
                    for plot in plots[station_name]:
                        self._dp.bot.send_photo(chat_id=user_id, photo=open(plot, 'rb'))
        logging.info('plots sent')
        self._new_users_waiting_for_plots = []


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
                        logging.info('Could not send message to user: {user_id}')

            logging.info('plots sent')
