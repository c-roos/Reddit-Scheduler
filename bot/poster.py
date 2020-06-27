import sys
import time
import configparser
import asyncio
import asyncpg
from models import RedditPost
import concurrent.futures
import signal
import logging


DB_CONFIG = 'db.ini'


class TermHandler():
    def __init__(self):
        self.exit_process = False
        signal.signal(signal.SIGTERM, self.set_exit_flag)
        
    def set_exit_flag(self, signum, frame):
        self.exit_process = True


async def get_db_connection():
    config = configparser.ConfigParser()
    config.read(DB_CONFIG)
    conn = await asyncpg.connect(
        user=config['DEFAULT']['user'],
        password=config['DEFAULT']['password'],
        host=config['DEFAULT']['host'],
        port=config['DEFAULT']['port'],
        database=config['DEFAULT']['database']
    )
    return conn


async def get_posts_from_db(connection):
    return await connection.fetch('SELECT * FROM scheduled WHERE posting_time <= $1 ORDER BY posting_time ASC', int(time.time()))
    
    
async def delete_from_db(connection, reddit_post):
    await connection.execute('DELETE FROM scheduled WHERE mid = $1', reddit_post.m_id)
    
    
async def update_for_retry(connection, reddit_post):
    await connection.execute(
        'UPDATE scheduled SET subreddits = $1, posting_time = $2 WHERE mid = $3',
        ', '.join(reddit_post.subreddits),
        int(time.time()) + 600,
        reddit_post.m_id
    )

    
def row_to_reddit_post(row):
    params = dict(row)
    params['mid'] = int(params['mid'])
    params['uid'] = int(params['uid'])
    params['subreddits'] = params['subreddits'].split(', ')
    reddit_post = RedditPost(params)
    return reddit_post
    
    
def submit(reddit_post):
    return reddit_post.submit_all()


def posting_loop(queue):
    # Set temination signal handler
    handler = TermHandler()
    
    # Get DB connection
    try:
        conn = asyncio.get_event_loop().run_until_complete(get_db_connection())
    except asyncio.exceptions.TimeoutError:
        sys.exit(1)
    
    #time.sleep(10)
    
    # Main loop
    while True:
        try:
            if handler.exit_process:
                asyncio.get_event_loop().run_until_complete(conn.close())
                break
            
            # Get post data from DB
            rows = asyncio.get_event_loop().run_until_complete(get_posts_from_db(conn))
            
            # Turn returned rows into RedditPost objects
            reddit_posts = [row_to_reddit_post(row) for row in rows]
            
            # Use thread pool to post
            if len(reddit_posts):
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    future_to_post = {executor.submit(submit, reddit_post): reddit_post for reddit_post in reddit_posts}
                    for future in concurrent.futures.as_completed(future_to_post):
                        post = future_to_post[future]
                        try:
                            code, msg = future.result()
                        except Exception as e:
                            logging.exception('Error getting future result')
                            asyncio.get_event_loop().run_until_complete(delete_from_db(conn, post))
                            queue.put((post.u_id, f"Unexpected Error while posting `{post.title}`. Please verify and reschedule"))
                        else:
                            if code == 2:
                                asyncio.get_event_loop().run_until_complete(update_for_retry(conn, post))
                                queue.put((post.u_id, msg))
                            else:
                                asyncio.get_event_loop().run_until_complete(delete_from_db(conn, post))
                                queue.put((post.u_id, msg))
                        
            # Sleep for a few seconds
            time.sleep(5)
            
        except Exception:
            logging.exception('Error in main loop')
            continue
