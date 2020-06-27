import discord
from discord.ext import commands, tasks
from utils import get_item_from_queue


class Replies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_queue.start()
    
    
    def cog_unload(self):
        self.check_queue.cancel()
        self.bot.post_queue.put(())
    
    
    @tasks.loop()
    async def check_queue(self):
        item = await self.bot.loop.run_in_executor(None, get_item_from_queue, self.bot.post_queue, self.bot.post_lock)
        if item:
            u_id, response = item
            user = self.bot.get_user(u_id)
            channel = user.dm_channel if user.dm_channel is not None else await user.create_dm()
            await channel.send(response)


def setup(bot):
    bot.add_cog(Replies(bot))
