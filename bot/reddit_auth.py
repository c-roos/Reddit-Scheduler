import random
import asyncio
import time
import boto3
import praw
import discord
from discord.ext import commands, tasks
from botocore.exceptions import ClientError
from utils import get_item_from_queue


WEB_APP = 'web_app'

SCOPES = ['identity submit']

GREEN_CHECK = '\U00002705'
    
    
def get_refresh_token(reddit, code):
    return reddit.auth.authorize(code)
    
    
def get_username(refresh_token):
    reddit = praw.Reddit(WEB_APP, refresh_token=refresh_token)
    return reddit.user.me().name
    
    
def update_user(author_id, reddit_username, refresh_token, table):  
    try:
        response = table.put_item(
            Item={
                'DiscordUserID': author_id,
                'RedditUsers': {reddit_username: refresh_token},
                'DefaultUser': reddit_username
            },
            ConditionExpression='attribute_not_exists(#id)',
            ExpressionAttributeNames={'#id': 'DiscordUserID'}
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            pass
        else:
            return e
    except Exception as e:
        return e
        
    try:
        response = table.update_item(
            Key={'DiscordUserID': author_id},
            UpdateExpression='set #ru.#usr = :tkn',
            ExpressionAttributeNames={
                '#ru': 'RedditUsers',
                '#usr': reddit_username
            },
            ExpressionAttributeValues={':tkn': refresh_token}
        )
    except ClientError as e:
        return e
    except Exception as e:
        return e

    return response


class RedditAuth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reddit = praw.Reddit(WEB_APP)
        self.states = {}
        
        dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
        self.user_table = dynamodb.Table('Users')
        self.check_queue.start()
    
    
    def cog_unload(self):
        self.check_queue.cancel()
        self.bot.auth_queue.put({})
    
    
    @commands.command(pass_context=True, aliases=['auth'], help="Authorize a reddit account.")
    async def authorize(self, ctx):
        state = random.randint(0, 99999)
        while state in self.states:
            state = random.randint(0, 99999)
        self.states[state] = (ctx, time.time())
            
        url = self.reddit.auth.url(SCOPES, str(state), "permanent")
        channel = ctx.author.dm_channel if ctx.author.dm_channel is not None else await ctx.author.create_dm()
        
        await ctx.send('Sending authorization url via DM...')
        await channel.send(f"Follow this link to authorize your account:\n{url}")
        
        await asyncio.sleep(600)
        
        try:
            _, timestamp = self.states[state]
        except KeyError:
            return
            
        if time.time() - timestamp >= 600:
            del self.states[state]


    @tasks.loop()
    async def check_queue(self):
        params = await self.bot.loop.run_in_executor(None, get_item_from_queue, self.bot.auth_queue, self.bot.auth_lock)
        try:
            ctx, _ = self.states.pop(params['state'])
        except KeyError:
            return
            
        try:
            code = params['code']
        except KeyError:
            return
        
        refresh_token = await self.bot.loop.run_in_executor(None, get_refresh_token, self.reddit, code)
        username = await self.bot.loop.run_in_executor(None, get_username, refresh_token)
        db_response = await self.bot.loop.run_in_executor(None, update_user, ctx.author.id, username.lower(), refresh_token, self.user_table)
        
        channel = ctx.author.dm_channel if ctx.author.dm_channel is not None else await ctx.author.create_dm()
        
        await channel.send(f"Successfully authorized Reddit account u/{username}")
        await ctx.send(f"Successfully authorized {ctx.author.name}'s Reddit account")
        
        
def setup(bot):
    bot.add_cog(RedditAuth(bot))
