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

    def __init__(self,token):

        # Create the Updater and pass it your bot's token.
        persistence = PicklePersistence(filename='backup/bot.pkl')
        self.updater = Updater(token, persistence=persistence)
        self._dp = self.updater.dispatcher

        self._dp.add_handler(CommandHandler('start',self._start))
        self._dp.add_handler(CommandHandler('subscribe',self._subscribe))
        self._dp.add_handler(CommandHandler('unsubscribe',self._unsubscribe))
        self._dp.add_handler(CommandHandler('where_am_I',self._get_ip_address))
        self._dp.add_handler(CommandHandler('conv',self._conv))


        subscription_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.regex('^(subscribe)$'), self._choose_station)],
            states={
                STATION: [MessageHandler(Filters.regex('^(Davos|Tschiertschen)$'), self._subscribe_for_station)],
                },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            )

        unsubscription_handler = ConversationHandler(
            entry_points=[MessageHandler(Filters.regex('^(unsubscribe)$'), self._unchoose_station)],
            states={
                STATION: [MessageHandler(Filters.regex('^(Davos|Tschiertschen)$'), self._unsubscribe_for_station)],
                },
            fallbacks=[CommandHandler('cancel', self._cancel)],
            )

        self._dp.add_handler(subscription_handler)
        self._dp.add_handler(unsubscription_handler)

        # start the bot
        self.updater.start_polling()

        self._new_users_waiting_for_plots = []


    def _conv(self,update: Update, context: CallbackContext):
        reply_keyboard = [['subscribe', 'unsubscribe']]

        reply_text = "Hi! I am OpenEns. I supply you with the latest ECWMF meteograms. \
                      As soon as the latest forecast is available I deliver them to you. \
                      Choose one of the following actions below."
        update.message.reply_text(reply_text,
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
        )

    def _unchoose_station(self,update: Update, context: CallbackContext) -> int:
        reply_keyboard = [['Davos', 'Tschiertschen']]

        reply_text = "Choose a station"
        update.message.reply_text(reply_text,
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
        )

        return STATION

    def _choose_station(self,update: Update, context: CallbackContext) -> int:
        reply_keyboard = [['Davos', 'Tschiertschen']]

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
        reply_text = f'Subscribed for Station {msg_text}'
        update.message.reply_text(reply_text,
        reply_markup=ReplyKeyboardRemove(),
        )
        self._register_subscription(user,msg_text,context)
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

    def _start(self,update: Update, context: CallbackContext):
        reply_text = "Hi! I am OpenEns. I supply you with the latest ECWMF meteograms. \
                      As soon as the latest forecast is available I deliver them to you. \
                      Currently I send you forecasts for Tschiertschen and Davos."

        reply_keyboard = [
            ['/subscribe'],[ '/unsubscribe']
        ]

        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
        user_id = update.effective_user.id

        update.message.reply_text(reply_text, reply_markup=markup)

    def _subscribe(self,update: Update, context: CallbackContext):
        reply_text = "You sucessfully subscribed. You will receive your first plots in a minute or two..."
        update.message.reply_text(reply_text)

        # add user to subscription list
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_id', set()) # create key if not present
        context.bot_data['user_id'].add(user_id)

        logging.info(context.bot_data.setdefault('user_id', set()))

        self._new_users_waiting_for_plots.append(user_id)

    def _unsubscribe(self,update: Update, context: CallbackContext):
        reply_text = "You sucessfully unsubscribed."
        update.message.reply_text(reply_text)

        # remove user from subscription list
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_id', set()) # create key if not present
        if user_id in context.bot_data['user_id']:
            context.bot_data['user_id'].remove(user_id)

        logging.info(context.bot_data.setdefault('user_id', set()))

    def _get_ip_address(self,update: Update, context: CallbackContext):
        ip_address = '';
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80))
        ip_address = s.getsockname()[0]
        s.close()

        reply_text = f"IP-ADDRESS: {ip_address}"
        update.message.reply_text(reply_text)

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
            logging.debug(user_id)
            for station_name in plots:
                message = station_name
                self._dp.bot.send_message(chat_id=user_id, text=message)
                for plot in plots[station_name]:
                    self._dp.bot.send_photo(chat_id=user_id, photo=open(plot, 'rb'))
        logging.info('plots sent')
        self._new_users_waiting_for_plots = []


    def broadcast(self,plots):
        if plots:
            for station_name in plots:
                message = station_name
                for user_id in self._dp.bot_data['user_id']:
                    logging.debug(user_id)
                    try:
                        self._dp.bot.send_message(chat_id=user_id, text=message)
                        for plot in plots[station_name]:
                            self._dp.bot.send_photo(chat_id=user_id, photo=open(plot, 'rb'))
                    except:
                        logging.info('Could not send message to user: {user_id}')

            logging.info('plots sent')
