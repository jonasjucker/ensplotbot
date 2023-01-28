import logging
import socket
import time

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    Updater,
    PicklePersistence,
    CallbackContext,
)

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

        # start the bot
        self.updater.start_polling()

    def _start(self,update: Update, context: CallbackContext):
        reply_text = "Hi! I am OpenEns. I supply you with the latest ECWMF meteograms. \
                      As soon as the latest forecast is available I deliver them to you. \
                      Currently only Tschiertschen is available. More to come soon..."

        reply_keyboard = [
            ['/subscribe'],[ '/unsubscribe']
        ]

        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
        user_id = update.effective_user.id

        update.message.reply_text(reply_text, reply_markup=markup)

    def _subscribe(self,update: Update, context: CallbackContext):
        reply_text = "You sucessfully subscribed."
        update.message.reply_text(reply_text)

        # add user to subscription list
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_id', set()) # create key if not present
        context.bot_data['user_id'].add(user_id)

        logging.info(context.bot_data.setdefault('user_id', set()))

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


    def broadcast(self,message,plots):
        if plots:
            for user_id in self._dp.bot_data['user_id']:
                logging.debug(user_id)
                self._dp.bot.send_message(chat_id=user_id, text=message)
                for plot in plots:
                    self._dp.bot.send_photo(chat_id=user_id, photo=open(plot, 'rb'))
            logging.info('plots sent')