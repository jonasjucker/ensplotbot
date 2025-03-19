#!/bin/bash

token=BOT_TOKEN

python main.py --bot_token $(cat $token) --bot_backup $(pwd)/backup --log_level 10 --admin_id $(cat ADMIN_ID)



