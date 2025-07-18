import os
import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from pyrogram.errors import (
    SessionPasswordNeeded,
    FloodWait,
    PhoneNumberInvalid,
    ApiIdInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
)
from dotenv import load_dotenv

# --- Basic Configuration ---
logging.basicConfig(
    format="[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s", level=logging.INFO
)
load_dotenv()

# --- Pyrogram Client Initialization ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Bot client
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory storage for user clients and conversation state
user_clients = {}
conversation_state = {}


# --- Bot Command Handlers ---
@bot.on_message(filters.command("start"))
async def start_handler(_, message: Message):
    """Handler for the /start command."""
    logging.info(f"User {message.from_user.id} started the bot.")
    await message.reply_text(
        "**Welcome to the Join Request Approver Bot! (Pyrogram Edition)**\n\n"
        "This bot can help you approve pending join requests for your channels and groups.\n\n"
        "**Available Commands:**\n"
        "▶️ `/login` - To log in with your user account.\n"
        "✅ `/approve` - To approve join requests after logging in.\n"
        "⏹️ `/logout` - To log out and delete your session.\n\n"
        "**⚠️ IMPORTANT:** This bot requires logging into your personal account to perform administrative actions. Please use it on a trusted server."
    )


@bot.on_message(filters.command("login"))
async def login_handler(client: Client, message: Message):
    """Handles the multi-step user login process."""
    user_id = message.from_user.id

    if user_id in user_clients:
        try:
            if user_clients[user_id].is_connected:
                await message.reply_text("✅ You are already logged in.")
                return
        except Exception:
            pass # Client might be disconnected, proceed with login

    conversation_state[user_id] = "awaiting_phone"
    await message.reply_text(
        "🚀 **Starting Login Process...**\n\nPlease enter your **phone number** (with country code, e.g., `+1234567890`):"
    )


@bot.on_message(filters.command("logout"))
async def logout_handler(_, message: Message):
    """Logs the user out and stops their client session."""
    user_id = message.from_user.id
    if user_id in user_clients:
        await message.reply_text("⏹️ Logging out...")
        await user_clients[user_id].stop()
        del user_clients[user_id]
        await message.reply_text("You have been successfully logged out.")
        logging.info(f"User {user_id} logged out.")
    else:
        await message.reply_text("You are not logged in.")


@bot.on_message(filters.command("approve"))
async def approve_handler(_, message: Message):
    """Lists chats where the user can approve join requests."""
    user_id = message.from_user.id
    if user_id not in user_clients:
        await message.reply_text("You need to `/login` first.")
        return

    user_client = user_clients[user_id]
    buttons = []
    
    await message.reply_text("⏳ Fetching your chats, please wait...")

    try:
        async for dialog in user_client.get_dialogs():
            if dialog.chat.type == enums.ChatType.CHANNEL or dialog.chat.type == enums.ChatType.GROUP:
                try:
                    member = await user_client.get_chat_member(dialog.chat.id, "me")
                    if member.privileges and member.privileges.can_invite_users:
                        buttons.append(
                            [
                                InlineKeyboardButton(
                                    dialog.chat.title,
                                    callback_data=f"approve_{dialog.chat.id}",
                                )
                            ]
                        )
                except Exception as e:
                    logging.warning(f"Could not check permissions for chat {dialog.chat.id}: {e}")

        if not buttons:
            await message.reply_text(
                "Couldn't find any channels or groups where you have permission to approve members."
            )
            return

        await message.reply_text(
            "**Select a chat to approve join requests:**",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        await message.reply_text(f"An error occurred while fetching chats: {e}")
        logging.error(f"Error fetching chats for user {user_id}: {e}")


@bot.on_callback_query(filters.regex(r"^approve_"))
async def approve_callback(_, callback_query: CallbackQuery):
    """Handles the button callback to approve requests for a specific chat."""
    user_id = callback_query.from_user.id
    if user_id not in user_clients:
        await callback_query.answer("Your session has expired. Please /login again.", show_alert=True)
        return

    user_client = user_clients[user_id]
    chat_id = int(callback_query.data.split("_")[1])
    
    await callback_query.message.edit_text("⏳ **Processing...**\nFetching and approving requests. This may take a moment.")

    try:
        approved_count = 0
        failed_count = 0
        
        async for request in user_client.get_chat_join_requests(chat_id):
            try:
                await user_client.approve_chat_join_request(chat_id, request.from_user.id)
                approved_count += 1
                await asyncio.sleep(1) # Delay to avoid flood waits
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await user_client.approve_chat_join_request(chat_id, request.from_user.id)
                approved_count += 1
            except Exception as e:
                failed_count += 1
                logging.warning(f"Failed to approve user {request.from_user.id} in chat {chat_id}: {e}")

        if approved_count == 0 and failed_count == 0:
            await callback_query.message.edit_text(f"✅ No pending join requests found for the selected chat.")
        else:
            await callback_query.message.edit_text(
                f"**Approval Complete!**\n\n"
                f"✅ Approved: **{approved_count}** new members.\n"
                f"❌ Failed: **{failed_count}** members."
            )
        logging.info(f"User {user_id} approved {approved_count} requests for chat {chat_id}.")

    except Exception as e:
        await callback_query.message.edit_text(f"❌ **Error:** Could not process approvals.\n`{e}`")
        logging.error(f"Error during approval for user {user_id}, chat {chat_id}: {e}")


# --- Conversation Handler for Login ---
@bot.on_message(filters.private & ~filters.command(["start", "login", "logout", "approve"]))
async def conversation_handler(client: Client, message: Message):
    """Manages the conversation flow for the login process."""
    user_id = message.from_user.id
    state = conversation_state.get(user_id)

    if not state:
        return

    if state == "awaiting_phone":
        try:
            phone_number = message.text
            # Create an in-memory user client
            user_client = Client(f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await user_client.connect()
            sent_code = await user_client.send_code(phone_number)
            
            conversation_state[user_id] = {
                "state": "awaiting_code",
                "phone": phone_number,
                "hash": sent_code.phone_code_hash,
                "client": user_client
            }
            await message.reply_text("A login code has been sent to your Telegram app. Please enter it here:")
        except PhoneNumberInvalid:
            await message.reply_text("❌ Invalid phone number. Please start again with `/login`.")
            del conversation_state[user_id]
        except Exception as e:
            await message.reply_text(f"An error occurred: {e}. Please start again with `/login`.")
            if "client" in conversation_state.get(user_id, {}):
                await conversation_state[user_id]["client"].disconnect()
            del conversation_state[user_id]

    elif isinstance(state, dict) and state.get("state") == "awaiting_code":
        code = message.text
        user_client = state["client"]
        try:
            await user_client.sign_in(state["phone"], state["hash"], code)
            user_clients[user_id] = user_client
            me = await user_client.get_me()
            await message.reply_text(f"✅ **Login successful!** Welcome, {me.first_name}.\nYou can now use the `/approve` command.")
            del conversation_state[user_id]
        except SessionPasswordNeeded:
            conversation_state[user_id]["state"] = "awaiting_password"
            await message.reply_text("Your account has 2FA enabled. Please enter your **password**:")
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await message.reply_text("❌ Invalid or expired code. Please start again with `/login`.")
            await user_client.disconnect()
            del conversation_state[user_id]
        except Exception as e:
            await message.reply_text(f"An error occurred: {e}. Please start again with `/login`.")
            await user_client.disconnect()
            del conversation_state[user_id]

    elif isinstance(state, dict) and state.get("state") == "awaiting_password":
        password = message.text
        user_client = state["client"]
        try:
            await user_client.check_password(password)
            user_clients[user_id] = user_client
            me = await user_client.get_me()
            await message.reply_text(f"✅ **Login successful!** Welcome, {me.first_name}.\nYou can now use the `/approve` command.")
            del conversation_state[user_id]
        except Exception as e:
            await message.reply_text(f"❌ Incorrect password or other error: {e}. Please start again with `/login`.")
            await user_client.disconnect()
            del conversation_state[user_id]


# --- Main Execution ---
async def main():
    """Main function to start the bot."""
    logging.info("Starting bot...")
    await bot.start()
    logging.info("Bot started successfully.")
    await asyncio.Event().wait() # Keep the bot running

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
