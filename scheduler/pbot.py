import sys
import multiprocessing as mp
import discord
from discord.ext import commands


TOKEN = 'YOUR DISCORD BOT TOKEN HERE'


def run_bot(auth_queue, post_queue):
    bot = commands.Bot(command_prefix='.', help_command=commands.DefaultHelpCommand(verify_checks=False))
    
    bot.launching = True
    bot.exit_code = 0
    bot.auth_queue = auth_queue
    bot.post_queue = post_queue
    bot.auth_lock = mp.Lock()
    bot.post_lock = mp.Lock()
    
    bot.load_extension('admin')
    
    bot.run(TOKEN)
    
    sys.exit(bot.exit_code)
