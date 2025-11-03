import asyncio
import os
import re
import random
from datetime import datetime
from aiohttp import web
from gemini_api import run_gemini_api, system_prompt
from database import log_message, get_user_history_async, init_db
from anti_spam import is_rate_limited
import requests
import json
from logging_setup import logger

# Đảm bảo init_db được gọi
init_db()

VERIFY_TOKEN = os.getenv("MESSENGER_VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN")

async def keep_alive(request):
    logger.info("Ping from UptimeRobot or test")
    return web.Response(text="Bot alive! No sleep pls~ 😴", status=200)

async def root_handler(request):
    logger.info("Root path accessed.")
    return web.Response(text="Bot is running! Use /keep-alive for health check.", status=200)

async def messenger_webhook(request):
    logger.info(f"Received request: {request.method} {request.url}")
    
    # Xử lý GET request (Xác minh Webhook)
    if request.method == 'GET':
        verify_token = request.query.get('hub.verify_token')
        challenge = request.query.get('hub.challenge')
        logger.info(f"Verify token: {verify_token}")
        if verify_token == VERIFY_TOKEN:
            return web.Response(text=challenge, status=200)
        logger.warning(f"Invalid verify token received: {verify_token}")
        return web.Response(text='Invalid verify token', status=403)
    
    # Xử lý POST request (Nhận tin nhắn)
    if request.method == 'POST':
        data = await request.json()
        logger.info(f"Webhook data: {json.dumps(data)}")
        if data['object'] == 'page':
            for entry in data['entry']:
                # Lặp qua TẤT CẢ messaging events
                for messaging in entry.get('messaging', []): 
                    sender_id = messaging['sender']['id']
                    
                    # KIỂM TRA ĐÂY CÓ PHẢI LÀ ECHO (bot tự gửi) hay không.
                    # BỎ QUA NGAY để tránh lỗi Messenger API (Lỗi 100)
                    if 'message' in messaging and messaging['message'].get('is_echo', False):
                        logger.info(f"Received message_echoes (bot's own message) from {sender_id}. Skipping.")
                        continue 

                    # 1. KIỂM TRA ĐÂY CÓ PHẢI LÀ TIN NHẮN (text message) hay không
                    if 'message' in messaging and 'text' in messaging['message']:
                        query = messaging['message'].get('text', '')
                        logger.info(f"Message from {sender_id}: {query}")
                        
                        # --- BẮT ĐẦU LOGIC XỬ LÝ TIN NHẮN CỦA BẠN ---
                        if await is_rate_limited(sender_id):
                            reply = "Úi, anh spam quá! Chờ xíu nha~ 😅"
                        else:
                            # Lấy lịch sử theo user_id
                            history = await get_user_history_async(sender_id)
                            messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": query}]
                            reply = await run_gemini_api(messages, os.getenv("MODEL_NAME"), sender_id, temperature=0.7, max_tokens=2000)
                            
                            # Xử lý Thinking Block (giữ nguyên logic của bạn)
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
                            if len(reply) > 2000:
                                reply = reply[:2000] + "... (cắt bớt nha!)"
                            
                            await log_message(sender_id, "assistant", reply)
                            
                        # Gửi reply qua Messenger API (giữ nguyên logic của bạn)
                        url = "https://graph.facebook.com/v20.0/me/messages"
                        headers = {'Content-Type': 'application/json'}
                        payload = {'access_token': PAGE_ACCESS_TOKEN, 'recipient': {'id': sender_id}, 'message': {'text': reply}}
                        response = requests.post(url, headers=headers, json=payload)
                        if response.status_code != 200:
                            logger.error(f"Messenger API error: {response.text}")
                        else:
                            logger.info(f"Sent reply to {sender_id}: {reply}")
                            
                    # 2. BỎ QUA CÁC SỰ KIỆN KHÔNG PHẢI TIN NHẮN (delivery, read, postback...)
                    else:
                        if 'delivery' in messaging:
                            logger.info(f"Received delivery event from {sender_id}. Skipping.")
                        elif 'read' in messaging:
                            logger.info(f"Received read event from {sender_id}. Skipping.")
                        elif 'postback' in messaging:
                            logger.info(f"Received postback event from {sender_id}. Skipping.")
                        else:
                            logger.warning(f"Received unhandled event from {sender_id}: {messaging}. Skipping.")

            return web.Response(text='OK', status=200)
        
app = web.Application()
app.router.add_get('/', root_handler)
app.router.add_get('/keep-alive', keep_alive)
app.router.add_route('*', '/messenger/webhook', messenger_webhook)

if __name__ == "__main__":
    try:
        port = os.environ.get('PORT')
        if port is None:
            logger.warning("PORT env var not set, using default 10000")
            port = '10000'
        port = int(port)
        logger.info(f"Starting server on port {port}")
        web.run_app(app, host='0.0.0.0', port=port)
    except ValueError as e:
        logger.error(f"PORT is not a valid number: {e}")
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}")