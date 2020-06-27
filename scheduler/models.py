import asyncio
import discord
import datetime
import asyncpg
from utils import retrieve_user_data
import praw
import prawcore.exceptions as ex
import urllib.request
import os
import time
import random
import logging


CHECK = '\U00002705'
RED_X = '\U0000274C'
EMOJIS = (CHECK, RED_X)

WEB_APP = 'web_app'


STORE_QUERY = ("INSERT INTO scheduled("
                   "mid, uid, posting_time, reddit_user, type, content, "
                   "subreddits, title, comment, flair_id, flair_text, "
                   "sort, crosspost, nsfw, spoiler, send_replies, pin, "
                   "pin_comment, lock"
               ") VALUES("
                   "$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, "
                   "$14, $15, $16, $17, $18, $19"
               ")")


'''"mid NUMERIC(64) PRIMARY KEY, "
             "uid NUMERIC(64), "
             "posting_time BIGINT, "
             "reddit_user VARCHAR(20), "
             "type TEXT, "
             "content TEXT, "
             "subreddits TEXT, "
             "title VARCHAR(300), "
             "comment VARCHAR(10000), "
             "flair_id TEXT, "
             "flair_text VARCHAR(64), "
             "sort TEXT, "
             "crosspost BOOLEAN, "
             "nsfw BOOLEAN, "
             "spoiler BOOLEAN, "
             "send_replies BOOLEAN, "
             "pin BOOLEAN, "
             "pin_comment BOOLEAN, "
             "lock BOOLEAN)" '''
             
ORANGERED = 16733952
  

class RedditPost:
    def __init__(self, parameters):
        self.m_id = parameters['mid']
        self.u_id = parameters['uid']
        self.posting_time = parameters['posting_time']
        self.reddit_user = parameters['reddit_user']
        self.submission_type = parameters['type']
        self.content = parameters['content']
        self.subreddits = parameters['subreddits']
        self.title = parameters['title']
        self.comment = parameters['comment']
        
        self.flair_id = parameters.get('flair_id')
        self.flair_text = parameters.get('flair_text')
        self.sort = parameters.get('sort')
        self.crosspost = parameters.get('crosspost', False)
        self.nsfw = parameters.get('nsfw', False)
        self.spoiler = parameters.get('spoiler', False)
        self.send_replies = parameters.get('send_replies', True)
        self.pin = parameters.get('pin', False)
        self.pin_comment = parameters.get('pin_comment', False)
        self.lock = parameters.get('lock', False)
        
        
    def _build_embed(self, author_avatar):
        embed = discord.Embed(
            description=('Please verify the details below.\nIf everything is '
                         'correct, press the check mark to confirm.'),
            color=ORANGERED
        )
        embed.set_thumbnail(url=author_avatar)
        if self.submission_type == 'image':
            embed.set_image(url=self.content)
        elif self.submission_type == 'video':
            embed.set_image(url=self.content.split(' ')[1])
        embed.set_author(name='Schedule Confirmation', icon_url='https://cdn.discordapp.com/avatars/708180723475021894/7c8a17b455ed9f04278a48eb17583085.webp')
        embed.add_field(name='Reddit Account', value=self.reddit_user, inline=False)
        embed.add_field(name='Subreddits', value=', '.join(self.subreddits), inline=False)
        embed.add_field(name='Posting Time', value=datetime.datetime.utcfromtimestamp(self.posting_time).strftime('%A %b %d, %I:%M %p UTC'), inline=False)
        embed.add_field(name='Title', value=self.title, inline=False)
        if self.comment is not None:
            embed.add_field(name='Comment', value=self.comment, inline=False)
            
        return embed
        
        
    async def confirm(self, ctx):
        embed = self._build_embed(ctx.author.avatar_url)
        
        m = await ctx.send(embed=embed)
        for emoji in EMOJIS:
            await m.add_reaction(emoji)
        
        def react_check(reaction, user):
            return reaction.message.id == m.id and user == ctx.author and reaction.emoji in EMOJIS
            
        try:
            reaction, user = await ctx.cog.bot.wait_for('reaction_add', timeout=30.0, check=react_check)
        except asyncio.TimeoutError:
            await ctx.send('Schedule canceled')
            return False
            
        if reaction.emoji == RED_X:
            await ctx.send('Schedule canceled')
            return False
        
        return True
        
        
    async def store(self, connection):
        await connection.execute(
            STORE_QUERY,
            self.m_id,
            self.u_id,
            self.posting_time,
            self.reddit_user,
            self.submission_type,
            self.content,
            ', '.join(self.subreddits),
            self.title,
            self.comment,
            self.flair_id,
            self.flair_text,
            self.sort,
            self.crosspost,
            self.nsfw,
            self.spoiler,
            self.send_replies,
            self.pin,
            self.pin_comment,
            self.lock
        )
    
    
    error_codes = {
        0: 'Success',
        1: 'User Error',
        2: 'Connection Error',
        3: 'Database Error',
        4: 'Unexpected Error',
        5: 'PRAW Error'
    }
    
    
    def _download_file(self, url):
        file_location = f"/dev/shm/{'_'.join(url.split('/')[-2:])}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Python3.8.2 (Ubuntu 20.04) schedulebot0.0'})
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return (1, f"The file at {url} has been deleted")
            else:
                logging.exception('Unexpected HTTP Error')
                return (4, f"Unexpected HTTP Error while downloading file: {url}")
        except Exception as e:
            logging.exception('Download Failed')
            return (4, f"Unexpected Error while dowloading file: {url}")
            
        # TODO: verify file type matches extension
            
        with open(file_location, 'wb') as f:
            f.write(response.read())
            
        return (0, file_location)
        
    
    def submit_all(self):
        # Get user data from DynamoDB
        user_data = retrieve_user_data(self.u_id)
        if user_data is None:
            return (1, 'User does not have any authorized Reddit accounts')
        
        # Get refresh token
        try:
            token = user_data['RedditUsers'][self.reddit_user]
        except KeyError:
            return (1, f"User is not authorized to use Reddit account: u/{self.reddit_user}")
            
        # Create authorized Reddit instance
        try:
            reddit = praw.Reddit(WEB_APP, refresh_token=token)
            _ = reddit.user.me()
        except ex.OAuthException:
            return (1, 'Refresh token no longer valid')
        except (ex.RequestException, ex.ResponseException):
            return (2, 'Could not connect to Reddit')
        except Exception as e:
            logging.exception('User Validation Failed')
            return (4, 'Unexpected Error')
            
        # Download files from Discord
        urls = self.content.split(' ')
        #media_url = urls[0]
        #media_file_name = '_'.join(media_url.split('/')[-2:])
        #media_file_location = f"/dev/shm/{media_file_name}"
        
        code, msg = self._download_file(urls[0])
        if code > 0:
            return (code, msg)
        self.media_file_location = msg
        
        if self.submission_type == 'video':
            code, msg = self._download_file(urls[1])
            if code > 0:
                return (code, msg)
            self.thumbnail_file_location = msg
           
        # req = urllib.request.Request(self.content, headers={'User-Agent': 'Python3.8.2 (Ubuntu 20.04) schedulebot0.0'})
        # try:
            # response = urllib.request.urlopen(req)
        # except urllib.error.HTTPError as e:
            # if e.code == 403:
                # return (1, f"The image at {self.content} has been deleted")
            # else:
                # logging.exception('Unexpected HTTP Error')
                # return (4, f"Unexpected HTTP Error while downloading image: {self.content}")
        # except Exception as e:
            # logging.exception('Download Failed')
            # return (4, f"Unexpected Error while dowloading image: {self.content}")
            
        # with open(file_location, 'wb') as f:
            # f.write(response.read())

        # Post image to each subreddit
        results = []
        for subreddit in self.subreddits:
            sub = reddit.subreddit(subreddit)
            results.append(self._submit_post(sub))
            time.sleep(random.randint(1,3))
            
        # Build reply message
        successes = '\n'.join(f"Successfully posted {link} to r/{subreddit} with u/{self.reddit_user}" for code, (link, subreddit) in results if code == 0)
        failures = '\n'.join(f"Error `{msg}` while trying to post `{self.title}` to r/{subreddit} with u/{self.reddit_user}" for code, (msg, subreddit) in results if code not in (0, 2))
        
        connection_errors = [subreddit for code, (_, subreddit) in results if code == 2]
        conn_errors_reply = '\n'.join(f"A connection error occurred while trying to post `{self.title}` to r/{subreddit}. Retrying in 10 minutes" for subreddit in connection_errors)
        
        reply = '\n\n'.join(s for s in (successes, failures, conn_errors_reply) if s)
        
        # Delete files
        os.remove(self.media_file_location)
        if self.submission_type == 'video':
            os.remove(self.thumbnail_file_location)
        
        # Return code and message
        if not connection_errors:
            return (0, reply)
        else:
            self.subreddits = connection_errors
            return (2, reply)
        
        
    def _submit_post(self, subreddit):
        try:
            if self.submission_type == 'image':
                submission = subreddit.submit_image(self.title, self.media_file_location, nsfw=self.nsfw, spoiler=self.spoiler, timeout=20)
            elif self.submission_type == 'video':
                submission = subreddit.submit_video(self.title, self.media_file_location, thumbnail_path=self.thumbnail_file_location, nsfw=self.nsfw, spoiler=self.spoiler, timeout=30)
        except (ex.RequestException, ex.ResponseException):
            return (2, ('Could not connect to Reddit', subreddit))
        except ex.Redirect:
            return (1, ('Subreddit does not exist', subreddit)) # this might not be possible
        except ex.Forbidden:
            return (1, ('You do not have access to this subreddit', subreddit))
        except praw.exceptions.RedditAPIException as e:
            errors = '\n'.join(f"{error.error_type}: {error.message}" for error in e.items)
            return (5, (errors, subreddit))
        except Exception as e:
            logging.exception('Submission Error')
            return (4, ('Unexpected Error', subreddit))
        
        if self.comment:
            try:
                submission.reply(self.comment)
            except Exception as e:
                logging.exception('Commenting Failed')
                
        return (0, (f"https://redd.it/{submission.id}", subreddit))
