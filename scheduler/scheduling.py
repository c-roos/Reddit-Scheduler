import importlib
import configparser
import typing
import random
import asyncio
import time
import datetime
import asyncpg
import praw
import discord
from discord.ext import commands, tasks
import boto3
from botocore.exceptions import ClientError
import checks
from converters import Timestamp, Subreddits, RedditUser
import models
from utils import retrieve_user_data


DB_CONFIG = 'db.ini'


SCHED_BRIEF = 'Schedule a Reddit Submission'
SCHED_HELP = ('Schedule a Reddit Submission'
              '\n\n<posting time> can either be a 10 digit unix timestamp representing a time to post at '
              'or a string in _D_H_M_S format representing an amount of time to wait until posting.'
              '\n<title> is the title of your post (use quotation marks if there are spaces).'
              '\n[user] is your reddit username. You must include the "u/". If omitted, your default account is used.'
              '\n[subreddits] is a list of subreddits to post to. You must start the list with "r/" and delimit separate subs with "+".'
              '\n[comment] is an optional comment to leave on your posts (use quotation marks if there are spaces).'
              '\n\nFor example, to schedule a post 1 day, 3 hours, and 20 minutes from now, to the subreddits r/sub1 and r/sub2, '
              'with the title "My Post", the account u/my_account, and a comment saying "This is my comment", you would use the following command:'
              '\n.schedule 1D3H20M "My Post" u/my_account r/sub1+sub2 "This is my comment"')
NOW_HELP = "This command is the same as schedule but you don't have to provide a posting time, because it posts now."
CANCEL_HELP = 'Cancel a scheduled submission.\n\n<message> is the url or ID of the message containing the command you scheduled the post with.'


class Scheduling(commands.Cog):
    def __init__(self, bot):
        importlib.reload(models)
        self.bot = bot
        self.bot.loop.create_task(self.ainit())
    
    
    async def ainit(self):
        config = configparser.ConfigParser()
        config.read(DB_CONFIG)
        try:
            self.pool = await asyncpg.create_pool(
                user=config['DEFAULT']['user'],
                password=config['DEFAULT']['password'],
                host=config['DEFAULT']['host'],
                port=config['DEFAULT']['port'],
                database=config['DEFAULT']['database']
            )
        except asyncio.exceptions.TimeoutError:
            self.pool = None
        
    
    def cog_unload(self):
        self.bot.loop.create_task(self.close_pool())
    
    
    async def close_pool(self):
        if self.pool is not None:
            await self.pool.close()
        
    
    async def get_user_data(self, user_id):
        return await self.bot.loop.run_in_executor(None, retrieve_user_data, user_id)
        
        
    async def request_thumbnail(self, ctx):
        def check(message):
            return message.channel == ctx.channel and message.author == ctx.author
    
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=120)
        except asyncio.TimeoutError:
            return None
        
        if msg.content.lower() == 'cancel':
            await ctx.send('Command canceled')
            return None
            
        if len(msg.attachments) == 0:
            await ctx.send("Error: `Missing Attachment`\nPlease upload an image to serve as your video's thumbnail now or type `cancel` to cancel")
            return await self.request_thumbnail(ctx)
            
        thumb_url = msg.attachments[0].url
        
        if not thumb_url.lower().endswith(('.jpg', '.png')):
            await ctx.send("Error: `Unsupported Thumbnail File Type`\nThumbnail must be one of the following types: jpg, png\nPlease upload an image to serve as your video's thumbnail now or type `cancel` to cancel")
            return await self.request_thumbnail(ctx)
            
        return thumb_url
    
    
    @checks.image_attached()
    @commands.command(pass_context=True, aliases=['sched', 's'], help=SCHED_HELP, brief=SCHED_BRIEF)
    async def schedule(self, ctx, posting_time: Timestamp, title, user: typing.Optional[RedditUser], subreddits: typing.Optional[Subreddits], comment=None):
        # Get user data from DynamoDB
        user_data = await self.get_user_data(ctx.author.id)
        
        # Handle unregistered users
        if user_data is None:
            await ctx.send('You have not authorized any Reddit accounts.\nYou can do so with the following command: `.auth`')
            return
        
        # Verify their selected Reddit account
        if user is None:
            user = user_data['DefaultUser']
        else:
            if user.lower() not in [name.lower() for name in user_data['RedditUsers'].keys()]:
                await ctx.send(f"You have not authorized the account u/{user}")
                return
        
        # Check for default subreddits if they didn't provide any
        if subreddits is None:
            try:
                subreddits = user_data['DefaultSubs']
            except KeyError:
                await ctx.send("You do not have any default subreddits set, so you must provide target subreddits in the command")
                
        # Determine media type
        media_url = ctx.message.attachments[0].url
        if media_url.lower().endswith(('.jpg', '.png', '.gif')):
            type = 'image'
        elif media_url.lower().endswith(('.mp4', '.webm')):
            type = 'video'
        else:
            await ctx.send('Error: `Unsupported File Type`\nFile must be one of the following types: jpg, png, gif, mp4, webm')
            return
            
        # Get thumbnail if video
        if type == 'video':
            if len(ctx.message.attachments) > 1:
                thumb_url = ctx.message.attachments[1].url
                if not thumb_url.lower().endswith(('.jpg', '.png')):
                    await ctx.send("Error: `Unsupported Thumbnail File Type`\nThumbnail must be one of the following types: jpg, png\nPlease upload an image to serve as your video's thumbnail now or type `cancel` to cancel")
                    thumb_url = await self.request_thumbnail(ctx) 
            else:
                await ctx.send("Please upload an image to serve as your video's thumbnail now or type `cancel` to cancel")
                thumb_url = await self.request_thumbnail(ctx)
                
            if thumb_url is None:
                return
                
            media_url += ' ' + thumb_url
                
        # Create RedditPost object
        parameters = {
            'mid': ctx.message.id,
            'uid': ctx.author.id,
            'posting_time': posting_time,
            'reddit_user': user,
            'type': type,
            'content': media_url,
            'subreddits': subreddits,
            'title': title,
            'comment': comment
        }
        post = models.RedditPost(parameters)
        
        # Confirm parameters are correct
        if not await post.confirm(ctx):
            return
        
        # Store in DB
        async with self.pool.acquire() as conn:
            await post.store(conn)
        
        await ctx.send('Confirmed')
        
    @checks.image_attached()
    @commands.command(pass_context=True, aliases=['n'], brief='Post as soon as possible', help=NOW_HELP)
    async def now(self, ctx, title, user: typing.Optional[RedditUser], subreddits: typing.Optional[Subreddits], comment=None):
        await self.schedule(ctx, int(time.time()), title, user, subreddits, comment)
        
        
    @schedule.error
    @now.error
    async def schedule_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send('You must attach an image to your message')
        else:
            await ctx.send(error)
        
        
    @commands.command(pass_context=True, aliases=['c'], brief='Cancel a Reddit Submission', help=CANCEL_HELP)
    async def cancel(self, ctx, message: discord.Message):
        if message.author.id != ctx.author.id:
            await ctx.send("You cannot cancel another user's submission")
            return
        
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM scheduled WHERE mid = $1", message.id)
        
        if result.endswith('0'):
            await ctx.send('No scheduled submission matching that message was found')
            return
        
        await ctx.send('Scheduled submission successfully canceled')
        
        
    @commands.command(pass_context=True, aliases=['posts'], help='View your scheduled Reddit Submissions')
    async def submissions(self, ctx):
        user_data = await self.get_user_data(ctx.author.id)
        
        if user_data is None:
            await ctx.send('You have not authorized any Reddit accounts.\nYou can do so with the following command: `.auth`')
            return
            
        usernames = tuple(user_data['RedditUsers'].keys())
        
        async with self.pool.acquire() as conn:
            results = await conn.fetch('SELECT mid, title, posting_time FROM scheduled WHERE reddit_user = ANY($1::varchar[]) ORDER BY posting_time ASC', usernames)
            
        reply = ''.join(f"```\nTitle: {row['title']}\nPosting Time: {datetime.datetime.utcfromtimestamp(row['posting_time']).strftime('%A %b %d, %I:%M %p UTC')}\nID: {row['mid']}\n```" for row in results)
        
        if not reply:
            await ctx.send('You do not have any submissions scheduled')
            return
            
        await ctx.send(reply)
        
        
def setup(bot):
    bot.add_cog(Scheduling(bot))