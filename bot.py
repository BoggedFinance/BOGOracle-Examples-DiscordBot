import asyncio
import datetime
import discord
import os
import requests
import sys
import threading
import yaml
from web3 import Web3
from dotenv import load_dotenv

# pull our secrets in
load_dotenv()

# pull our not-so-secrets in
with open("config.yml", "r") as yaml_in:
    configs = yaml.load(yaml_in, Loader=yaml.FullLoader)

# get a functioning contract object from just an address, courtesy of bscscan
# TODO: if we get rate limited or similar, start using a real API key
def get_contract(w3, address, abi_raw=None):
    if abi_raw == None:
        abi_url = f"https://api.bscscan.com/api?module=contract&action=getabi&address={address}&format=raw"
        abi_raw = requests.get(abi_url).content.decode("utf-8")
    contract = w3.eth.contract(address, abi=abi_raw)
    return contract, abi_raw


class DiscordW3ClientBot:
    """ marries a discord.Client(...) with a web3.Web3(...) """
    def __init__(self, token, guild_id, config):
        self.last_update_time = datetime.datetime.now()
        self.client = discord.Client()
        self.token = token
        self.guild_id = guild_id
        self.config = config
        self.abi = None
        self.on_ready = self.client.event(self.on_ready)

    async def on_ready(self):
        """ things we should only run once at startup """
        print(f'{self.config["token_name"]} connected as {self.client.user}')

        # add the periodic tasks that will check the oracle for a price and update status
        self.client.loop.create_task(self.status_task())
        self.client.loop.create_task(self.status_watchdog())

        # set the bot avatar, per config
        with open(self.config["avatar_file"], "rb") as avatar_in:
            avatar_data = avatar_in.read()
        await self.client.user.edit(username=f'{self.config["token_name"]}-Oraclebot', avatar=avatar_data)
    
    def calc_price_v1(self, oracle):
        """ oracle v1 algorithm """
        token_spot = oracle.functions.getSpotPrice().call()
        bnb_spot = oracle.functions.getBNBSpotPrice().call()

        token_price = (1000000 / token_spot) * (1000000 / bnb_spot)
        return token_price

    def calc_price_v2(self, oracle, use_bnb_spot=False):
        """ oracle v2 algorithm """
        
        # in case we just want the bnb spot price
        if use_bnb_spot:
            token_spot = oracle.functions.getBNBSpotPrice().call()
        else:
            token_spot = oracle.functions.getSpotPrice().call()
        token_decimals = oracle.functions.getDecimals().call()

        # apply correct number of decimals to get the human-readable value
        token_price = token_spot / (10 ** token_decimals)
        return token_price


    async def _apply_presence(self, presence_str):
        activity = discord.Activity(type=discord.ActivityType.watching,
                                    name=presence_str)
        return await self.client.change_presence(activity=activity)


    async def apply_thinking_presence(self, count):
        """ updates the thinking spinner and references bogtools.io """
        # add a unique char that changes on each iter so you can tell if the bot is updating or stale
        thinking_chars = "⣾⣽⣻⢿⡿⣟⣯⣷"
        think_char = thinking_chars[count % len(thinking_chars)]
        think_str = f"{think_char} bogtools.io oracle"
        return await self._apply_presence(think_str)


    async def status_watchdog(self):
        """ periodic task that ensures status_task keeps running """
        try:
            while True:
                await asyncio.sleep(5)
                now = datetime.datetime.now()
                if (now - self.last_update_time).total_seconds() > 15:
                    await self._apply_presence("ERROR: data may be stale!")

        except Exception as e:
            print(f"watchdog raised exception: {e}")
            print(f"not safe to continue without a watchdog, exiting!")
            sys.exit(1)


    async def status_task(self):
        """ periodic task that fetches price and updates the bot's data """

        count = 0
        while True:
            count += 1

            # this is lazy, but I don't want these to go down again
            # Swallow any and all exceptions for now; the show must go on!
            # TODO: handle errors more gracefully (issue #6)
            try:
                await self.apply_thinking_presence(count)
                if count % 2 == 0:
                    w3 = Web3(Web3.HTTPProvider(self.config["bsc_rpc_url"]))
                    oracle, abi = get_contract(w3, self.config["oracle_address"], self.abi)
                    self.abi = abi
                    guild = self.client.get_guild(id=self.guild_id)
                    member = guild.get_member(self.client.user.id)

                    token_price = 0
                    if self.config["oracle_version"] == 1:
                        token_price = self.calc_price_v1(oracle)
                    else:
                        token_price = self.calc_price_v2(oracle, self.config["token_name"] == "BNB")

                    await member.edit(nick=f"{self.config['token_name']}: ${token_price:0.2f}")
                    self.last_update_time = datetime.datetime.now()
            except Exception as e:
                print(f"!!!!!!!! exception on count {count}")
                print(e)
                print("sleep 10s and carry on")
                await asyncio.sleep(10)

            await asyncio.sleep(6)

    def start(self):
        return self.client.start(self.token)


# async is fun!
loop = asyncio.get_event_loop()

# each bot gets a DiscordW3ClientBot instance
for key in configs:
    config = configs[key]
    bot_token = os.getenv(config['discord_token_key'])
    guild_id = int(os.getenv('GUILD_ID'))
    client = DiscordW3ClientBot(bot_token, guild_id, config)
    loop.create_task(client.start())

# see you, space cowboy
loop.run_forever()
