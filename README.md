# bog-oracle-discobot
Using $BOG oracles to show live price in a discord bot

## Setup

1. Install python3.8 (or higher) and pip
1. Determine your discord server's Guild ID and add to `.env` as `GUILD_ID=YOURID`
1. For each token you want to track in a bot:
    1. Create an app on discord: https://discord.com/developers/applications
    1. Add a bot to the app
    1. Copy the bot token and add `MY_BOT_TOKEN=YOURTOKENHERE` to `.env` according to the `discord_token_key` you have set in your config.yml
    1. **DO NOT COMMIT .env!** This would allow anyone to hijack your bots!
1. (optional) make a virtualenv: `virtualenv .venv && source .venv/bin/activate`
1. If you are on a cloud provider, you may need: `apt install python3.8-dev build-essential`
1. `pip install -r requirements.txt`

## Run

`python bot.py`

(note: on a cloud provider you may want to use `nohup` to ensure the bot continues running
after you have disconnected, but a future release here will include upstart documentation)

## Install as a systemd service

The discordbot can also be installed as an auto-restarting service in systemd:

1. `sudo cp ~/path/to/existing/BOGOracle-Examples-DiscordBot /opt/BOGOracle-Examples-DiscordBot`
1. `sudo chown youruser:youruser /opt/BOGOracle-Examples-DiscordBot`
1. `sudo cp /opt/BOGOracle-Examples-DiscordBot/systemd/bog-discord-bot.service /etc/systemd/system/bog-discord-bot.service`
1. `sudo systemctl start bog-discord-bot`
1. Confirm it is running: `sudo systemctl status bog-discord-bot`