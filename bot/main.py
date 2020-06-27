import time
import logging
import multiprocessing as mp
from poster import posting_loop
from listen import listen
import pbot


logging.basicConfig(filename='bot.log', format='%(asctime)s %(levelname)s:%(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.ERROR)


def main():
    while True:
        auth_queue = mp.Queue()
        post_queue = mp.Queue()
        
        listener_process = mp.Process(target=listen, args=('ec2-3-21-163-184.us-east-2.compute.amazonaws.com', 80, auth_queue))
        listener_process.start()

        poster_process = mp.Process(target=posting_loop, args=(post_queue,))
        poster_process.start()
        
        bot_process = mp.Process(target=pbot.run_bot, args=(auth_queue, post_queue))
        bot_process.start()
        
        bot_process.join()
        
        listener_process.terminate()
        listener_process.join()
        
        poster_process.terminate()
        poster_process.join()
        
        if bot_process.exitcode == 1:
            time.sleep(3)
            continue
        else:
            break


if __name__ == '__main__':
    main()
