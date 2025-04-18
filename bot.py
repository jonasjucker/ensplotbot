import asyncio

from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import (CommandHandler, MessageHandler, Application, filters,
                          ConversationHandler, CallbackContext, ContextTypes)

from logger_config import logger
from constants import TIMEOUT_IN_SEC, STATION_SELECT_ONE_TIME, STATION_SELECT_SUBSCRIBE, ONE_TIME, SUBSCRIBE, UNSUBSCRIBE, VALID_SUMMARY_INTERVALS, JOBQUEUE_DELAY


class PlotBot:

    def __init__(self,
                 token,
                 station_config,
                 db=None,
                 admin_id=None,
                 ecmwf=None):

        self._admin_id = admin_id
        self.app = Application.builder().token(token).build()
        self._db = db
        self._ecmwf = ecmwf
        self._station_names = sorted(
            [station["name"] for station in station_config])
        self._region_of_stations = {
            station["name"]: station["region"]
            for station in station_config
        }
        self._station_regions = sorted(
            {station["region"]
             for station in station_config})
        # filter for stations
        self._filter_stations = filters.Regex("^(" +
                                              "|".join(self._station_names) +
                                              ")$")
        # filter for regions
        self._filter_regions = filters.Regex("^(" +
                                             "|".join(self._station_regions) +
                                             ")$")
        # filter for all commands of bot
        self._filter_all_commands = filters.Regex(
            "^(/locations|/subscribe|/unsubscribe|/plots|/help|/cancel|/start|/stats)$"
        )

        # filter for meaningful messages that are explicitly handled by the bot
        # inverse of all filters above
        self._filter_meaningful_messages = ~self._filter_all_commands & ~self._filter_regions & ~self._filter_stations

        self.app.add_handler(CommandHandler('start', self._help))
        self.app.add_handler(CommandHandler('help', self._help))
        self.app.add_handler(CommandHandler('cancel', self._cancel))
        self.app.add_handler(CommandHandler('stats', self._stats))
        self.app.add_handler(
            CommandHandler('locations', self._overview_locations))

        # add help handler for all other messages
        self.app.add_handler(
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
            conversation_timeout=TIMEOUT_IN_SEC,
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
            conversation_timeout=TIMEOUT_IN_SEC,
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
            conversation_timeout=TIMEOUT_IN_SEC,
        )

        self.app.add_handler(subscription_handler)
        self.app.add_handler(unsubscription_handler)
        self.app.add_handler(one_time_forecast_handler)
        self.app.add_error_handler(self._error)

        self.app.job_queue.run_once(
            self._override_basetime,
            when=0,
            name='Override basetime',
        )
        self.app.job_queue.run_repeating(
            self._update_basetime,
            interval=60,
            first=60,
            name='Update basetime',
        )
        self.app.job_queue.run_repeating(
            self._cache_plots,
            interval=30,
            first=30,
            name='Cache plots',
        )
        self.app.job_queue.run_repeating(
            self._broadcast_from_queue,
            interval=90,
            first=60,
            name='Broadcast',
        )

    async def _override_basetime(self, context: CallbackContext):
        logger.info('Overriding basetime')
        self._ecmwf.override_base_time_from_init()

    async def _update_basetime(self, context: CallbackContext):
        logger.info('Updating basetime')
        self._ecmwf.upgrade_basetime_global()
        self._ecmwf.upgrade_basetime_stations()

    async def _send_plot_from_queue(self, context: CallbackContext):
        job = context.job
        user_id, station_name = job.data
        plots = self._ecmwf.download_plots([station_name])
        await self._send_plot_to_user(plots, station_name, user_id)

    def start(self):
        logger.info('Starting bot')
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    async def _error(self, update: Update, context: CallbackContext):
        #user_id = update.message.chat_id
        logger.error(f"Exception while handling an update: {context.error}")
        #self._db.log_activity(
        #    activity_type="bot-error",
        #    user_id=user_id,
        #    station="unknown",
        #)

    async def _stats(self, update: Update, context: CallbackContext):
        user_id = update.message.chat_id
        if user_id != self._admin_id:
            await update.message.reply_text(
                "You are not authorized to view stats.")
            return

        activity_summary_text = []
        activity_summary_text.append('*Activity summary*')
        for interval in VALID_SUMMARY_INTERVALS:
            activity_summary = self._db.get_activity_summary(interval)
            activity_summary_text.append(f"_{interval.lower()}_")
            for activity in activity_summary:
                activity_summary_text.append(f"- {activity}")
            activity_summary_text.append('')
        activity_summary_text = "\n".join(activity_summary_text)
        await update.message.reply_markdown(activity_summary_text)

    async def _overview_locations(self, update: Update,
                                  context: CallbackContext):
        await update.message.reply_markdown("\n".join(
            self._available_locations()))

    def _available_locations(self):
        text = ["_Available locations_"]
        for location in self._station_regions:
            text.append(f'')
            text.append(f'*{location}*')
            text.extend([
                f'- {n}' for n in self._get_station_names_for_region(location)
            ])
        return text

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

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

        await update.message.reply_markdown(greetings)

    async def _choose_station(self, update: Update,
                              context: CallbackContext) -> int:
        region = update.message.text
        station_of_region = self._get_station_names_for_region(region)

        user_id = update.message.chat_id

        # Get the stations that the user has already subscribed to
        subscribed_stations = self._db.get_subscriptions_by_user(user_id)

        # Only include stations that the user has not already subscribed to
        not_subscribed_for_all_stations = await self._send_station_keyboard(
            update, [
                name for name in station_of_region
                if name not in subscribed_stations
            ])

        return SUBSCRIBE if not_subscribed_for_all_stations else ConversationHandler.END

    async def _choose_all_region(self, update: Update,
                                 context: CallbackContext) -> int:

        entry_point = update.message.text

        await self._send_region_keyboard(
            update, [name for name in self._station_regions])

        # check that entry point is valid
        if entry_point == '/subscribe':
            return STATION_SELECT_SUBSCRIBE
        elif entry_point == '/plots':
            return STATION_SELECT_ONE_TIME
        else:
            raise ValueError(f'Invalid entry point: {entry_point}')

    def _get_station_names_for_region(self, region) -> list[str]:
        return sorted([
            name for name in sorted(self._station_names)
            if self._region_of_stations[name] == region
        ])

    async def _choose_all_station(self, update: Update,
                                  context: CallbackContext) -> int:
        region = update.message.text

        await self._send_station_keyboard(
            update, self._get_station_names_for_region(region))

        return ONE_TIME

    async def _revoke_station(self, update: Update,
                              context: CallbackContext) -> int:
        user_id = update.message.chat_id

        # Get the stations that the user has already subscribed to
        subscribed_stations = self._db.get_subscriptions_by_user(user_id)

        # Only include stations that the user has already subscribed to
        subscription_present = await self._send_station_keyboard(
            update,
            sorted([
                name for name in self._station_names
                if name in subscribed_stations
            ]))

        return UNSUBSCRIBE if subscription_present else ConversationHandler.END

    async def _send_region_keyboard(self, update: Update,
                                    region_names: list[str]):
        return await self._send_keyboard(update, region_names, 'region')

    async def _send_keyboard(self, update: Update, names: list[str],
                             type: str):
        reply_keyboard = [[name] for name in names]

        if reply_keyboard:
            reply_text = f'Choose a {type}'
            await update.message.reply_text(
                reply_text,
                reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                 one_time_keyboard=True),
            )
            return True
        else:
            await update.message.reply_text(
                f"Sorry, no more {type}s for you here",
                reply_markup=ReplyKeyboardRemove())
            return False

    async def _send_station_keyboard(self, update: Update,
                                     station_names: list[str]):
        return await self._send_keyboard(update, station_names, 'station')

    async def _unsubscribe_for_station(self, update: Update,
                                       context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        self._db.remove_subscription(msg_text, user.id)

        reply_text = f'Unubscribed for Station {msg_text}'
        await update.message.reply_text(
            reply_text,
            reply_markup=ReplyKeyboardRemove(),
        )
        logger.info(f' {user.first_name} unsubscribed for Station {msg_text}')

        self._db.log_activity(
            activity_type="unsubscription",
            user_id=user.id,
            station=msg_text,
        )

        return ConversationHandler.END

    async def _subscribe_for_station(self, update: Update,
                                     context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        reply_text = f"You sucessfully subscribed for {msg_text}. You will receive your first plots in a minute or two..."
        await update.message.reply_text(
            reply_text,
            reply_markup=ReplyKeyboardRemove(),
        )
        self._db.add_subscription(msg_text, user.id)

        logger.info(f' {user.first_name} subscribed for Station {msg_text}')
        context.job_queue.run_once(self._send_plot_from_queue,
                                   JOBQUEUE_DELAY,
                                   data=(user.id, msg_text))

        self._db.log_activity(
            activity_type="subscription",
            user_id=user.id,
            station=msg_text,
        )

        return ConversationHandler.END

    async def _request_one_time_forecast_for_station(
            self, update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        msg_text = update.message.text
        reply_text = f"You sucessfully requested a forecast for {msg_text}. You will receive your first plots in a minute or two..."
        await update.message.reply_text(
            reply_text,
            reply_markup=ReplyKeyboardRemove(),
        )

        context.job_queue.run_once(self._send_plot_from_queue,
                                   JOBQUEUE_DELAY,
                                   data=(user.id, msg_text))
        logger.info(
            f' {user.first_name} requested forecast for Station {msg_text}')

        self._db.log_activity(
            activity_type="one-time-request",
            user_id=user.id,
            station=msg_text,
        )

        return ConversationHandler.END

    async def _cancel(self, update: Update, context: CallbackContext) -> int:
        user = update.message.from_user
        logger.info("User %s canceled the conversation.", user.first_name)
        await update.message.reply_text(
            'Bye! I hope we can talk again some day.',
            reply_markup=ReplyKeyboardRemove())

        return ConversationHandler.END

    async def _cache_plots(self, context: CallbackContext):
        self._ecmwf.cache_plots()

    async def _send_plot_to_user(self, plots, station_name, user_id):
        logger.debug(f'Send plot to user: {user_id}')
        try:
            await self.app.bot.send_message(chat_id=user_id, text=station_name)
            for plot in plots[station_name]:
                await self.app.bot.send_photo(chat_id=user_id,
                                              photo=open(plot, 'rb'))
        except Exception as e:
            logger.error(f'Error sending plot to user {user_id}: {e}')

    async def _broadcast_from_queue(self, context: CallbackContext):
        plots = self._ecmwf.download_latest_plots(
            self._db.stations_with_subscribers())
        if plots:
            for station_name in plots:
                for user_id in self._db.get_subscriptions_by_station(
                        station_name):
                    await self._send_plot_to_user(plots, station_name, user_id)
            logger.info('plots sent to all users')
