#!/bin/bash

token=BOT_TOKEN

python main.py --bot_token $(cat $token) --bot_backup $(pwd)/backup --log_level 20 --admin_id 1007789003



