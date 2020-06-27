import discord
from discord.ext import commands, tasks


cogs = ['admin', 'reddit_auth', 'scheduling', 'replies']


class Admin(commands.Cog, command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.launching:
            for cog in cogs:
                if cog != 'admin':
                    self.bot.load_extension(cog)
            self.bot.launching = False
        
        
    @commands.command(pass_context=True, help="Reload cogs")
    @commands.is_owner()
    async def reload(self, ctx):
        errors = False
        loaded = list(self.bot.extensions.keys())
        for cog in loaded:
            try:
                self.bot.reload_extension(cog)
            except Exception as e:
                errors = True
                await ctx.send(e)
        
        for cog in cogs:
            if cog in loaded:
                continue
            try:
                self.bot.load_extension(cog)
            except Exception as e:
                errors = True
                await ctx.send(e)
        
        if not errors:
            await ctx.send('\U00002705')
    
    
    @commands.command(pass_context=True, help='Restart bot and related processes')
    @commands.is_owner()
    async def restart(self, ctx):
        await ctx.send('Restarting...')
        self.bot.exit_code = 1
        await self.bot.logout()


    @commands.command(pass_context=True, help='Shutdown bot')
    @commands.is_owner()
    async def shutdown(self, ctx):
        await ctx.send('Shutting down...')
        self.bot.exit_code = 0
        await self.bot.logout()


def setup(bot):
    bot.add_cog(Admin(bot))
