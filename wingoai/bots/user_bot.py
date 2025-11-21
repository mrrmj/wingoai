from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import requests
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("USER_BOT_TOKEN")

app = Client(
    "user_bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

# Registration links
REG_LINK = "https://51game6.in/#/register?invitationCode=811214253486"
LOGIN_LINK = "https://51game6.in/#/login"
DEPOSIT_LINK = "https://51game6.in/#/wallet/Recharge"
DEP_HISTORY_LINK = "https://51game6.in/#/wallet/RechargeHistory"
MAIN_PAGE = "https://51game6.in/#/"
WINGO_30S = "https://51game6.in/#/saasLottery/WinGo?gameCode=WinGo_30S&lottery=WinGo"
WINGO_1M = "https://51game6.in/#/saasLottery/WinGo?gameCode=WinGo_1M&lottery=WinGo"
WINGO_3M = "https://51game6.in/#/saasLottery/WinGo?gameCode=WinGo_3M&lottery=WinGo"
WINGO_5M = "https://51game6.in/#/saasLottery/WinGo?gameCode=WinGo_5M&lottery=WinGo"

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    welcome_text = f"""
🎉 Welcome to WinGo AI Prediction Bot!

To use this service, you need to:
1. Register at: {REG_LINK}
2. Login: {LOGIN_LINK}
3. Deposit minimum 500 INR: {DEPOSIT_LINK}
4. Check deposit history: {DEP_HISTORY_LINK}

After deposit, use /verify to submit verification request.

Available Game Types:
- /predict30s - 30 Second WinGo
- /predict1m - 1 Minute WinGo  
- /predict3m - 3 Minute WinGo
- /predict5m - 5 Minute WinGo
- /predictall - All predictions
    """
    await message.reply_text(welcome_text)

@app.on_message(filters.command("verify"))
async def verify_command(client: Client, message: Message):
    await message.reply_text("""
To verify your account, please send:
1. Your Platform UID
2. Deposit Screenshot (minimum 500 INR)

Send your UID first, then the screenshot.
    """)

@app.on_message(filters.text & ~filters.command)
async def handle_uid(client: Client, message: Message):
    # Check if this is a UID (assuming it's a number)
    text = message.text.strip()
    if text.isdigit() and len(text) >= 8:  # Basic UID validation
        # Store UID temporarily (in a real app, use a database)
        # For now, just acknowledge
        await message.reply_text(f"UID received: {text}\nNow please send your deposit screenshot.")
        # In a real implementation, store this UID with the user's TG ID

@app.on_message(filters.photo)
async def handle_screenshot(client: Client, message: Message):
    # Save the screenshot
    file_path = f"uploads/{message.from_user.id}_{message.id}.jpg"
    await message.download(file_path)
    
    # Send verification request to backend
    tg_id = str(message.from_user.id)
    uid = "temp_uid"  # This should be retrieved from temporary storage
    
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                "http://localhost:8000/verify-request",
                data={
                    "tg_id": tg_id,
                    "uid": uid
                },
                files={
                    "screenshot": f
                }
            )
        
        if response.status_code == 200:
            await message.reply_text("Verification request submitted successfully! Please wait for admin approval.")
        else:
            await message.reply_text("Error submitting verification request. Please try again.")
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

@app.on_message(filters.command("status"))
async def status_command(client: Client, message: Message):
    tg_id = str(message.from_user.id)
    
    try:
        response = requests.get(f"http://localhost:8000/user/status/{tg_id}")
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            if status == "verified":
                await message.reply_text("✅ Your account is verified! You can now use prediction services.")
            elif status == "not_verified":
                await message.reply_text("⚠️ Your account is not verified. Please use /verify to submit verification request.")
            elif status == "not_registered":
                await message.reply_text("❌ You are not registered. Please use /start to get started.")
            else:
                await message.reply_text("❓ Status unknown. Please try again.")
        else:
            await message.reply_text("Error checking status. Please try again.")
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

@app.on_message(filters.command("predict30s"))
async def predict_30s_command(client: Client, message: Message):
    await send_prediction(message, "30sec")

@app.on_message(filters.command("predict1m"))
async def predict_1m_command(client: Client, message: Message):
    await send_prediction(message, "1min")

@app.on_message(filters.command("predict3m"))
async def predict_3m_command(client: Client, message: Message):
    await send_prediction(message, "3min")

@app.on_message(filters.command("predict5m"))
async def predict_5m_command(client: Client, message: Message):
    await send_prediction(message, "5min")

@app.on_message(filters.command("predictall"))
async def predict_all_command(client: Client, message: Message):
    try:
        response = requests.get("http://localhost:8000/predict")
        if response.status_code == 200:
            data = response.json()
            response_text = "📊 All Predictions:\n\n"
            
            for game_type, pred in data.items():
                if "message" not in pred:
                    color = pred["color"]
                    confidence = pred["confidence"]
                    safe = pred["safe"]
                    status_text = "✅ SAFE" if safe else "❌ AVOID"
                    response_text += f"{game_type.upper()}:\nPeriod: {pred['period']}\nColor: {color}\nConfidence: {confidence:.2f}\nStatus: {status_text}\n\n"
                else:
                    response_text += f"{game_type.upper()}: {pred['message']}\n\n"
            
            await message.reply_text(response_text)
        else:
            await message.reply_text("Error fetching predictions. Please try again.")
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

async def send_prediction(message: Message, game_type: str):
    try:
        response = requests.get(f"http://localhost:8000/predict/{game_type}")
        if response.status_code == 200:
            data = response.json()
            if "period" in 
                color = data["color"]
                confidence = data["confidence"]
                safe = data["safe"]
                
                status_text = "✅ SAFE" if safe else "❌ AVOID"
                game_display = game_type.replace('sec', ' Second').replace('min', ' Minute').upper()
                await message.reply_text(f"""
📊 {game_display} Prediction:
Period: {data["period"]}
Color: {color}
Confidence: {confidence:.2f}
Status: {status_text}
                """)
            else:
                await message.reply_text(f"No {game_type} predictions available yet.")
        else:
            await message.reply_text("Error fetching prediction. Please try again.")
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

if __name__ == "__main__":
    app.run()