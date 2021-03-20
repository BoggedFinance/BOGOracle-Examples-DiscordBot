import asyncio
import discord
import os
import requests
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
def get_contract(w3, address):
    abi_url = f"https://api.bscscan.com/api?module=contract&action=getabi&address={address}&format=raw"
    abi_raw = requests.get(abi_url).content.decode("utf-8")
    contract = w3.eth.contract(address, abi=abi_raw)
    return contract


class DiscordW3ClientBot:
    """ marries a discord.Client(...) with a web3.Web3(...) """
    def __init__(self, token, guild_id, config):
        self.client = discord.Client()
        self.token = token
        self.guild_id = guild_id
        self.config = config
        self.on_ready = self.client.event(self.on_ready)

    async def on_ready(self):
        """ things we should only run once at startup """
        print(f'{self.config["token_name"]} connected as {self.client.user}')

        # add the periodic task that will check the oracle for a price
        self.client.loop.create_task(self.status_task())

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

    async def apply_presence(self, count):
        """ updates the thinking spinner and references bogtools.io """

        # add a unique char that changes on each iter so you can tell if the bot is updating or stale
        thinking_chars = "⣾⣽⣻⢿⡿⣟⣯⣷"
        activity = discord.Activity(type=discord.ActivityType.watching,
                                    name=f"{thinking_chars[count % len(thinking_chars)]} bogtools.io oracle")
        return await self.client.change_presence(activity=activity)


    async def status_task(self):
        """ periodic task that fetches price and updates the bot's data """

        count = 0
        while True:
            w3 = Web3(Web3.HTTPProvider(self.config["bsc_rpc_url"]))
            oracle = get_contract(w3, self.config["oracle_address"])
            guild = self.client.get_guild(id=self.guild_id)
            member = guild.get_member(self.client.user.id)

            token_price = 0
            if self.config["oracle_version"] == 1:
                token_price = self.calc_price_v1(oracle)
            else:
                token_price = self.calc_price_v2(oracle, self.config["token_name"] == "BNB")

            await self.apply_presence(count)
            await member.edit(nick=f"{self.config['token_name']}: ${token_price:0.2f}")
            count += 1
            
            # give the free APIs we are using a break
            await asyncio.sleep(10)

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
