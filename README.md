# Reddit-Scheduler
A multi-process program for scheduling Reddit submissions via Discord

## How It Works
This program is intended to be a public web app that allows users to schedule submissions to Reddit. The backend runs on an AWS EC2 instance, while Amazon DynamoDB and RDS are used for user and scheduling data respectively.
Users will be able to interact with the app though a Discord bot. 

The Reddit scheduler is composed of 4 processes: a main process, a discord bot, an HTTP listener, and a Reddit poster.

### Main
The main process handles launching, restarting, and terminating the other processes.

### Discord Bot
The Discord bot is the frontend of the app. Users can utilize various commands to do things like authorize the app to post with their Reddit account, create a text post on Reddit, access their user data stored on DynamoDB, upload a video to their reddit profile, etc.

### HTTP Listener
The listener is a simple HTTP listener written in Python to handle OAuth callbacks from Reddit, allowing users to easily authorize the app. It also communicates with the Discord bot to let users know when they've successfully authorized the app.

### Reddit Poster
The posting process handles the previously scheduled posts, creating the Reddit submissions at the appropriate time. It's capable of uploading eight files to Reddit concurrently. It also communicates with the Discord bot to let users know the status of their scheduled posts.
