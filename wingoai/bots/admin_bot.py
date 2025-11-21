from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import requests
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("ADMIN_BOT_TOKEN")
admin_tg_id = os.getenv("ADMIN_TG_ID")

app = Client(
    "admin_bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    if str(message.from_user.id) != admin_tg_id:
        await message.reply_text("❌ You are not authorized to use this bot!")
        return
    
    await message.reply_text("✅ Admin bot is ready! Use /requests to see pending verification requests.")

@app.on_message(filters.command("requests"))
async def show_requests(client: Client, message: Message):
    if str(message.from_user.id) != admin_tg_id:
        await message.reply_text("❌ You are not authorized to use this bot!")
        return
    
    try:
        response = requests.get("http://localhost:8000/admin/verify-requests")
        if response.status_code == 200:
            requests_data = response.json()
            pending_requests = [r for r in requests_data if r["status"] == "pending"]
            
            if not pending_requests:
                await message.reply_text("✅ No pending verification requests.")
                return
            
            for req in pending_requests:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{req['id']}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{req['id']}")
                    ]
                ])
                
                await message.reply_photo(
                    photo=req["screenshot_path"],
                    caption=f"""
📝 Verification Request #{req['id']}
👤 Telegram ID: {req['tg_id']}
🔢 UID: {req['uid_submitted']}
🕐 Submitted: {req['created_at']}
                    """,
                    reply_markup=keyboard
                )
        else:
            await message.reply_text("Error fetching requests. Please try again.")
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

@app.on_callback_query()
async def handle_callback(client: Client, callback_query):
    if str(callback_query.from_user.id) != admin_tg_id:
        await callback_query.answer("❌ You are not authorized!", show_alert=True)
        return
    
    data = callback_query.data
    if data.startswith("approve_") or data.startswith("reject_"):
        request_id = int(data.split("_")[1])
        action = "approve" if data.startswith("approve_") else "reject"
        
        try:
            response = requests.post(
                "http://localhost:8000/admin/verify",
                data={
                    "request_id": request_id,
                    "action": action
                }
            )
            
            if response.status_code == 200:
                await callback_query.answer(f"Request {action}d successfully!", show_alert=True)
                
                # Update the message
                await callback_query.edit_message_caption(
                    caption=callback_query.message.caption + f"\n\n✅ Status: {action.upper()}d"
                )
            else:
                await callback_query.answer("Error processing request!", show_alert=True)
        except Exception as e:
            await callback_query.answer(f"Error: {str(e)}", show_alert=True)

if __name__ == "__main__":
    app.run()