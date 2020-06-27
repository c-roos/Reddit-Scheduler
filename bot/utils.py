import logging
import urllib.request
import boto3


def retrieve_user_data(discord_id):
    session = boto3.session.Session()
    dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
    table = dynamodb.Table('Users')
    
    key = {'DiscordUserID': discord_id}
    
    try:
        response = table.get_item(Key=key)
    except Exception:
        logging.exception('DynamoDB Error')
        return None
    else:
        return response.get('Item')
        

def get_item_from_queue(queue, lock):
    with lock:
        item = queue.get()
    return item
