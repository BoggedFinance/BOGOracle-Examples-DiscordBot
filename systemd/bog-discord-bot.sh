#!/bin/bash
VENV_ACTIVATE=/opt/BOGOracle-Examples-DiscordBot/.venv/bin/activate
if [ -f "$VENV_ACTIVATE" ]; then
    . $VENV_ACTIVATE
else
    echo "No venv to activate, using base python"
fi

BOT_SCRIPT=/opt/BOGOracle-Examples-DiscordBot/bot.py
echo "Starting $BOT_SCRIPT"
python $BOT_SCRIPT