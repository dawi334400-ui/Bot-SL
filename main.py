import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

token = "MTU1MzAwOTMzNzAxNzA0MDk5Ng.GkoRWt.FRsJP1QMp-84HctzRyJvQX713ho54sSggOC3gA"
bot.run(token)
