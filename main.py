import os
import asyncio
import logging
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import ChatjoinRequests
from dotenv import load_dotenv

# Handle varying import paths for different Telethon versions
try:
    from telethon.tl.functions.channels import GetChatjoinRequestsRequest
except ImportError:
    from telethon.tl.functions.messages import GetChatjoinRequestsRequest

try:
    from telethon.tl.functions.messages import HideChatJoinRequestRequest
except ImportError:
    from telethon.tl.functions.channels import HideChatJoinRequestRequest


# --- Basic Configuration ---
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# --- Load Environment Variables ---
# Create a .env file in the same directory with your API_ID, API_HASH, and BOT_TOKEN
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- In-memory storage for user clients and conversation state ---
# In a real-world scenario, you might want to use a database for this.
user_clients = {}
# Dictionary to prevent multiple login processes for the same user
user_login_locks = {}


# --- Main Bot Client Initialization ---
try:
    bot = TelegramClient('bot_session', int(API_ID), API_HASH).start(bot_token=BOT_TOKEN)
except Exception as e:
    logging.error(f"Failed to start the bot: {e}")
    exit(1)

# --- Bot Command Handlers ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    """Handler for the /start command."""
    sender = await event.get_sender()
    logging.info(f"User {sender.id} started the bot.")
    await event.reply(
        "**Welcome to the Join Request Approver Bot!**\n\n"
        "This bot can help you approve pending join requests for your channels and groups.\n\n"
        "**Available Commands:**\n"
        "▶️ `/login` - To log in with your user account.\n"
        "✅ `/approve` - To approve join requests after logging in.\n"
        "⏹️ `/logout` - To log out and delete your session.\n\n"
        "**⚠️ IMPORTANT:** This bot requires logging into your personal account to perform administrative actions. Please use it on a trusted server. See the README for more details."
    )

@bot.on(events.NewMessage(pattern='/login'))
async def login_handler(event):
    """Handles the multi-step user login process."""
    sender = await event.get_sender()
    user_id = sender.id

    # Prevent starting a new login if one is already in progress
    if user_id in user_login_locks and not user_login_locks[user_id].is_set():
        await event.reply("A login process is already active. Please complete or cancel it first.")
        return
    
    login_lock = asyncio.Event()
    user_login_locks[user_id] = login_lock

    # Check if user is already logged in and connected in memory
    if user_id in user_clients:
        client = user_clients[user_id]
        try:
            if client.is_connected() and await client.is_user_authorized():
                await event.reply("✅ You are already logged in.")
                login_lock.set()
                return
        except Exception as e:
            logging.warning(f"Re-login required for user {user_id}: {e}")
            del user_clients[user_id]


    session_file = f'{user_id}.session'
    client = TelegramClient(session_file, int(API_ID), API_HASH)
    is_connected = False

    try:
        await client.connect()
        is_connected = True

        # If session is valid, no need to ask for credentials
        if await client.is_user_authorized():
            user_clients[user_id] = client
            me = await client.get_me()
            await event.reply(f"✅ Welcome back, {me.first_name}! You are already logged in.")
            logging.info(f"User {user_id} ({me.first_name}) reconnected via session file.")
            login_lock.set()
            return

        # If not authorized, start the full login flow
        await event.reply("🚀 **Starting Login Process...**\nPlease follow the instructions carefully.")
        
        async with bot.conversation(sender, timeout=300) as conv:
            # 1. Ask for Phone Number
            await conv.send_message("Please enter your **phone number** (with country code, e.g., +1234567890):")
            phone_number = (await conv.get_response()).text.strip()

            # 2. Send Code
            try:
                code_request = await client.send_code_request(phone_number)
            except Exception as e:
                await conv.send_message(f"❌ **Error:** Failed to send code. Please check the phone number and try again.\n`{e}`")
                login_lock.set()
                return

            # 3. Ask for Telegram Code
            await conv.send_message("A login code has been sent to your Telegram app. Please enter it here:")
            code = (await conv.get_response()).text.strip()

            # 4. Sign In
            try:
                await client.sign_in(phone_number, code, phone_code_hash=code_request.phone_code_hash)
            except SessionPasswordNeededError:
                # 5. Ask for 2FA Password if needed
                await conv.send_message("Your account has 2FA enabled. Please enter your **password**:")
                password = (await conv.get_response()).text.strip()
                try:
                    await client.sign_in(password=password)
                except Exception as e:
                    await conv.send_message(f"❌ **Error:** Login failed. Incorrect password or other issue.\n`{e}`")
                    login_lock.set()
                    return
            except Exception as e:
                await conv.send_message(f"❌ **Error:** Login failed. Incorrect code or other issue.\n`{e}`")
                login_lock.set()
                return

        if await client.is_user_authorized():
            user_clients[user_id] = client
            me = await client.get_me()
            await event.reply(f"✅ **Login successful!** Welcome, {me.first_name}.\nYou can now use the `/approve` command.")
            logging.info(f"User {user_id} ({me.first_name}) logged in successfully.")
        else:
            await event.reply("❌ **Login failed.** Something went wrong. Please try again.")

    except asyncio.TimeoutError:
        await event.reply("Login process timed out. Please start again with `/login`.")
    except Exception as e:
        await event.reply(f"An unexpected error occurred: {e}")
        logging.error(f"Login error for user {user_id}: {e}")
    finally:
        # If login failed but client is connected, disconnect it.
        # If successful, leave it connected and stored in user_clients.
        if user_id not in user_clients and is_connected:
            await client.disconnect()
        login_lock.set() # Release the lock

@bot.on(events.NewMessage(pattern='/approve'))
async def approve_handler(event):
    """Lists chats where the user can approve join requests."""
    sender = await event.get_sender()
    user_id = sender.id

    if user_id not in user_clients:
        await event.reply("You need to `/login` first. If you have logged in before, try again as your session might have expired.")
        return
    
    client = user_clients[user_id]
    
    try:
        if not client.is_connected():
            await client.connect()
        if not await client.is_user_authorized():
            await event.reply("Your session has expired. Please `/login` again.")
            return
    except Exception as e:
        await event.reply(f"Could not verify your session. Please `/login` again. Error: {e}")
        return


    buttons = []
    
    await event.reply("⏳ Fetching your chats, please wait...")

    try:
        async for dialog in client.iter_dialogs():
            if dialog.is_channel or dialog.is_group:
                entity = dialog.entity
                # Check for admin rights, specifically the right to invite users (which covers approving joins)
                if hasattr(entity, 'admin_rights') and entity.admin_rights and entity.admin_rights.invite_users:
                    buttons.append([Button.inline(f"{dialog.name}", data=f"approve_{entity.id}")])
        
        if not buttons:
            await event.reply("Couldn't find any channels or groups where you have permission to approve members.")
            return

        await event.reply("**Select a chat to approve join requests:**", buttons=buttons)

    except Exception as e:
        await event.reply(f"An error occurred while fetching chats: {e}")
        logging.error(f"Error fetching chats for user {user_id}: {e}")


@bot.on(events.CallbackQuery(pattern=b"approve_"))
async def approve_callback(event):
    """Handles the button callback to approve requests for a specific chat."""
    sender = await event.get_sender()
    user_id = sender.id

    if user_id not in user_clients:
        await event.answer("Your session has expired. Please /login again.", alert=True)
        return

    client = user_clients[user_id]
    chat_id = int(event.data.decode('utf-8').split('_')[1])

    await event.edit("⏳ **Processing...**\nFetching and approving requests. This may take a moment.")

    try:
        target_chat = await client.get_entity(chat_id)
        approved_count = 0
        failed_count = 0
        
        # Use the raw API request for broader compatibility
        result = await client(GetChatjoinRequestsRequest(
            peer=target_chat,
            offset_date=None,
            offset_user=await client.get_input_entity('me'), # A dummy value is often needed
            limit=200 # Process up to 200 at a time
        ))
        
        # Create a mapping from user_id to the full user object for the approval function
        users_map = {user.id: user for user in result.users}
        
        if not hasattr(result, 'requests') or not result.requests:
             await event.edit(f"✅ No pending join requests found for **{target_chat.title}**.")
             return

        for request in result.requests:
            user_id_to_approve = request.user_id
            try:
                # Use the more compatible raw API call to approve the request
                await client(HideChatJoinRequestRequest(
                    peer=target_chat,
                    user_id=users_map[user_id_to_approve],
                    approved=True
                ))
                approved_count += 1
                await asyncio.sleep(1) # Add a small delay to avoid hitting API limits
            except Exception as e:
                failed_count += 1
                logging.warning(f"Failed to approve user {user_id_to_approve} in chat {chat_id}: {e}")

        await event.edit(
            f"**Approval Complete for {target_chat.title}!**\n\n"
            f"✅ Approved: **{approved_count}** new members.\n"
            f"❌ Failed: **{failed_count}** members."
        )
        logging.info(f"User {user_id} approved {approved_count} requests for chat {chat_id}.")

    except Exception as e:
        await event.edit(f"❌ **Error:** Could not process approvals.\n`{e}`")
        logging.error(f"Error during approval for user {user_id}, chat {chat_id}: {e}")


@bot.on(events.NewMessage(pattern='/logout'))
async def logout_handler(event):
    """Logs the user out and deletes their session file."""
    sender = await event.get_sender()
    user_id = sender.id
    session_file = f'{user_id}.session'

    if user_id in user_clients:
        await user_clients[user_id].log_out()
        del user_clients[user_id]
    
    if os.path.exists(session_file):
        os.remove(session_file)
        
    await event.reply("⏹️ **You have been logged out.**\nYour session file has been deleted from the server.")
    logging.info(f"User {user_id} logged out.")


# --- Main Execution ---
async def main():
    """Main function to start the bot."""
    logging.info("Bot started...")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    bot.loop.run_until_complete(main())
