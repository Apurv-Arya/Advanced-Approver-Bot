Telegram Join Request Approver Bot
This is a Python-based Telegram bot that helps channel and group administrators approve pending join requests.

The bot allows an administrator to securely log into their own Telegram account through the bot. Once authenticated, the bot can act on their behalf to list their channels/groups and approve all pending join requests for a selected chat with a single command.

🔴 SECURITY WARNING 🔴

This bot requires you to log in with your personal Telegram account credentials (API_ID, API_HASH, and phone number). This information is sensitive and grants the bot full access to your account.

NEVER run this bot on a server you do not own or trust completely.

NEVER give your credentials to a public instance of this bot.

The credentials are used to create a .session file which authenticates the bot to act on your behalf. Protect this file as you would a password.

The author of this script is not responsible for any misuse or loss of data. You are running this at your own risk.

Features
Secure User Login: Multi-step login process via the bot, including handling 2-Factor Authentication (2FA).

Session Persistence: User sessions are saved locally, so you don't have to log in every time the bot restarts.

Dynamic Chat Selection: Automatically lists the channels and groups where you have permission to approve new members.

Bulk Approval: Approves all pending join requests for a selected chat in one go.

Logout: Ability to log out and delete your session file from the bot.

Setup Instructions
1. Prerequisites
Python 3.8 or newer.

A Telegram account.

2. Get Telegram API Credentials
You need to get your own API_ID and API_HASH from Telegram. Do not confuse these with the bot token.

Go to my.telegram.org and log in with your phone number.

Click on "API development tools".

Fill in the "App title" and "Short name" (you can choose any name).

You will get your api_id and api_hash. Keep these safe.

3. Create a Telegram Bot
Open Telegram and search for the @BotFather bot.

Start a chat and send the /newbot command.

Follow the instructions to choose a name and username for your bot.

BotFather will give you a Bot Token. Keep this safe.

4. Prepare the Bot Server
Clone or download the bot script to your server.

Create a file named .env in the same directory as the script. This file will store your credentials securely. Add the following lines to it, replacing the placeholders with your actual credentials:

API_ID=1234567
API_HASH=your_api_hash_from_telegram
BOT_TOKEN=your_bot_token_from_botfather

Install the required Python libraries:

pip install -r requirements.txt

5. Run the Bot
Once the setup is complete, you can run the bot with the following command:

python main.py

If everything is configured correctly, you will see a message saying "Bot started..." and your bot will be live on Telegram.

How to Use the Bot
/start: Shows the welcome message.

/login: Initiates the login process for your personal Telegram account. The bot will ask you for:

Your phone number (in international format, e.g., +1234567890).

The login code sent to your Telegram app.

Your 2FA password, if you have one enabled.
Once you complete the process, your session is saved.

/approve: After logging in, use this command to start approving members.

The bot will show you a list of your channels and groups where you have the necessary permissions.

Click the button corresponding to the chat you want to manage.

The bot will then fetch and approve all pending join requests for that chat and send you a confirmation.

/logout: Logs you out of the bot. This will stop any active session and delete your .session file from the server, revoking the bot's access to your account.