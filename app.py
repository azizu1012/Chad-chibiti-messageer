import asyncio
import threading
import os
import re
import random
from flask import Flask
import requests
import json
from aiohttp import web
from gemini_api import run_gemini_api, system_prompt
from database import log_message, get_user_history_async, init_db
from anti_spam import is_rate_limited
from logging_setup import logger  # Giả định từ file logging_setup.py cũ

init_db()

# Flask cho keep-alive (UptimeRobot)
keep_alive_app = Flask(__name__)
VERIFY_TOKEN = os.getenv("MESSENGER_VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN")

@keep_alive_app.route('/keep-alive', methods=['GET'])
def keep_alive():
    return "Bot alive! No sleep pls~ 😴", 200

# Aiohttp cho Messenger webhook
async def messenger_webhook(request):
    if request.method == 'GET':
        verify_token = request.query.get('hub.verify_token')
        challenge = request.query.get('hub.challenge')
        if verify_token == VERIFY_TOKEN:
            return web.Response(text=challenge, status=200)
        return web.Response(text='Invalid verify token', status=403)
    if request.method == 'POST':
        data = await request.json()
        if data['object'] == 'page':
            for entry in data['entry']:
                messaging = entry['messaging'][0]
                sender_id = messaging['sender']['id']
                query = messaging['message'].get('text', '')
                # Check anti-spam
                if await is_rate_limited(sender_id):
                    reply = "Úi, anh spam quá! Chờ xíu nha~ 😅"
                else:
                    # Gọi Gemini logic
                    history = await get_user_history_async(sender_id)
                    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": query}]
                    reply = await run_gemini_api(messages, os.getenv("MODEL_NAME"), sender_id, temperature=0.7, max_tokens=2000)
                    thinking_block_pattern = r'<THINKING>(.*?)</THINKING>'
                    thinking_match = re.search(thinking_block_pattern, reply, re.DOTALL)
                    if thinking_match:
                        logger.info(f"--- THINKING DEBUG FOR USER: {sender_id} ---")
                        logger.info(thinking_match.group(1).strip())
                        logger.info("--- END THINKING DEBUG ---")
                        reply = re.sub(thinking_block_pattern, '', reply, flags=re.DOTALL).strip()
                    if not reply:
                        friendly_errors = [
                            "Úi chà! 🥺 Tui bị lỗi đường truyền xíu ròi! Hỏi lại nha!",
                            "Ôi không! 😭 Tui đơ mất tiêu, hỏi lại tui nha! ✨",
                            "Ái chà chà! 🤯 Mất sóng rồi, thử lại nha anh! 😉"
                        ]
                        reply = random.choice(friendly_errors)
                    if len(reply) > 2000:  # Messenger limit
                        reply = reply[:2000] + "... (cắt bớt nha!)"
                    # Log message
                    await log_message(sender_id, "assistant", reply)
                # Gửi reply qua Messenger API
                url = "https://graph.facebook.com/v20.0/me/messages"
                headers = {'Content-Type': 'application/json'}
                payload = {'access_token': PAGE_ACCESS_TOKEN, 'recipient': {'id': sender_id}, 'message': {'text': reply}}
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"Messenger API error: {response.text}")
        return web.Response(text='OK', status=200)

# Chạy Flask và Aiohttp song song
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    keep_alive_app.run(host='0.0.0.0', port=port, debug=False)

async def run_aiohttp():
    app = web.Application()
    app.router.add_route('*', '/messenger/webhook', messenger_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 3978)))
    await site.start()

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    asyncio.run(run_aiohttp())