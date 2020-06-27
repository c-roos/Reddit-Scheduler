import re
import time
from discord.ext import commands


MINUTE = 60
HOUR = 3600
DAY = 86400


class Timestamp(commands.Converter):
    async def convert(self, ctx, argument):
        if re.match(r"^[0-9]{10}$", argument, re.I):
            stamp = int(argument)
            if stamp < time.time():
                raise commands.BadArgument(message='Timestamp has already passed')
            return stamp
            
        match = re.match(r"^(?!$)(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$", argument, re.I)
        if match:
            
            seconds = 0
            if match.group(1): # days
                seconds += int(match.group(1)) * DAY
            if match.group(2): # hours
                seconds += int(match.group(2)) * HOUR
            if match.group(3): # minutes
                seconds += int(match.group(3)) * MINUTE
            if match.group(4): # seconds
                seconds += int(match.group(4))
            return time.time() + seconds
        
        raise commands.BadArgument(message='Properly formatted posting time not provided')
        
        
class Subreddits(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.startswith('r/'):
            return argument[2:].split('+')
        raise commands.BadArgument(message='Not a list of subreddits')
        
        
class RedditUser(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.startswith('u/'):
            return argument[2:].lower()
        raise commands.BadArgument(message='Not a Reddit username')