import asyncio
import datetime
import discord
import json
import os
import requests
import sys
import traceback
import yaml
from web3 import Web3
from dotenv import load_dotenv

BOGINFO_ABI = json.loads('[{"inputs":[],"name":"getBNBSpotPrice","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"}],"name":"getPair","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"adr","type":"address"}],"name":"getTokenInfo","outputs":[{"internalType":"string","name":"name","type":"string"},{"internalType":"string","name":"symbol","type":"string"},{"internalType":"uint8","name":"decimals","type":"uint8"},{"internalType":"uint256","name":"totalSupply","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"}],"name":"getTokenTokenPrice","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"PRICE_DECIMALS","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]')
BOGINFO_ADDR = "0x0Bd91f45FcA6428680C02a79A2496D6f97BDF24a"
WBNB_ADDR = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"

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
        self.w3 = Web3(Web3.HTTPProvider(self.config["bsc_rpc_url"]))
        self.oracle = self.w3.eth.contract(BOGINFO_ADDR, abi=BOGINFO_ABI)
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
        await self._apply_presence("Initializing...")
        await self._apply_nick("Initializing...")
        await self.client.user.edit(username=f'{self.config["token_name"]}-Oraclebot', avatar=avatar_data)
    
    def calc_price(self, token_addr):
        wbnb_price = self.oracle.functions.getBNBSpotPrice().call() / 10 ** 18
        if token_addr == WBNB_ADDR:
            return wbnb_price
        token_token_price = self.oracle.functions.getTokenTokenPrice(token_addr, WBNB_ADDR).call() / 10 ** 18
        return token_token_price * wbnb_price

    async def _apply_presence(self, presence_str):
        activity = discord.Activity(type=discord.ActivityType.watching,
                                    name=presence_str)
        return await self.client.change_presence(activity=activity)

    async def apply_thinking_presence(self, count):
        """ updates the thinking spinner and references bogtools.io """
        # add a unique char that changes on each iter so you can tell if the bot is updating or stale
        if not self.updates_are_stalled():
            thinking_chars = "⣾⣽⣻⢿⡿⣟⣯⣷"
            think_char = thinking_chars[count % len(thinking_chars)]
            think_str = f"{think_char} bogtools.io oracle"
            return await self._apply_presence(think_str)

    def updates_are_stalled(self):
        return (datetime.datetime.now() - self.last_update_time).total_seconds() > 24  # 2 web3 polling cycles = 24s

    async def status_watchdog(self):
        """ periodic task that ensures status_task keeps running """
        try:
            while True:
                await asyncio.sleep(5)
                if self.updates_are_stalled():
                    await self._apply_presence("ERROR: data may be stale!")

        except Exception as e:
            traceback.print_exc()
            print(f"watchdog raised exception: {e}")
            print(f"not safe to continue without a watchdog, exiting!")
            sys.exit(1)

    async def _apply_nick(self, nick_str):
        guild = self.client.get_guild(id=self.guild_id)
        member = guild.get_member(self.client.user.id)
        await member.edit(nick=nick_str)


    async def status_task(self):
        """ periodic task that fetches price and updates the bot's data """

        count = 0
        while True:
            count += 1

            # this is lazy, but I don't want these to go down again
            # Swallow any and all exceptions for now; the show must go on!
            # TODO: handle errors more gracefully (issue #6)
            try:
                if count % 2 == 0:

                    token_price = self.calc_price(self.config['token_addr'])
                    
                    self.last_update_time = datetime.datetime.now()
                    await self._apply_nick(f"{self.config['token_name']}: ${token_price:0.2f}")
                await self.apply_thinking_presence(count)
            except Exception as e:
                print(f"!!!!!!!! exception on count {count}")
                traceback.print_exc()
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
