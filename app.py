import asyncio
import os
import re
import random
from aiohttp import web
from gemini_api import run_gemini_api, system_prompt
from database import log_message, get_user_history_async, init_db
from anti_spam import is_rate_limited
import requests
import json
from logging_setup import logger

init_db()

VERIFY_TOKEN = os.getenv("MESSENGER_VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN")

async def keep_alive(request):
    logger.info("Ping from UptimeRobot or test")
    return web.Response(text="Bot alive! No sleep pls~ 😴", status=200)

async def messenger_webhook(request):
    logger.info(f"Received request: {request.method} {request.url}")
    if request.method == 'GET':
        verify_token = request.query.get('hub.verify_token')
        challenge = request.query.get('hub.challenge')
        logger.info(f"Verify token: {verify_token}")
        if verify_token == VERIFY_TOKEN:
            return web.Response(text=challenge, status=200)
        return web.Response(text='Invalid verify token', status=403)
    if request.method == 'POST':
        data = await request.json()
        logger.info(f"Webhook data: {json.dumps(data)}")
        if data['object'] == 'page':
            for entry in data['entry']:
                messaging = entry['messaging'][0]
                sender_id = messaging['sender']['id']
                query = messaging['message'].get('text', '')
                logger.info(f"Message from {sender_id}: {query}")
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
                else:
                    logger.info(f"Sent reply to {sender_id}: {reply}")
        return web.Response(text='OK', status=200)

app = web.Application()
app.router.add_get('/keep-alive', keep_alive)
app.router.add_route('*', '/messenger/webhook', messenger_webhook)

if __name__ == "__main__":
    web.run_app(app, host='0.0.0.0', port=int(os.environ.get('PORT', 3978)))