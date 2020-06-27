from discord.ext import commands


FILE_EXTS = ('jpg', 'png', 'gif', '.webm', '.mp4')


def tuesday_channel():
    async def predicate(ctx):
        return ctx.channel.id == ctx.cog.tuesday_channel
    return commands.check(predicate)
    
    
def approved_user():
    async def predicate(ctx):
        return ctx.author.id in ctx.cog.approved
    return commands.check(predicate)
    
    
def image_attached():
    async def predicate(ctx):
        files = ctx.message.attachments
        if not files:
            return False
        if not files[0].filename.lower().endswith(FILE_EXTS):
            return False
        return True
    return commands.check(predicate)