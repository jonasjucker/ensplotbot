#!/bin/bash
python main.py --bot_token $(cat BOT_TOKEN) --bot_backup $(pwd)/backup --log_level 10 --admin_id $(cat ADMIN_ID)



