import asyncio
import os
import re
import random
from datetime import datetime
from aiohttp import web, ClientSession
from gemini_api import run_gemini_api, get_system_prompt # system_prompt is now a function
from database import log_message, get_user_history_async, init_db, close_db_connection
from anti_spam import is_rate_limited
import json
from logging_setup import logger
from tools import close_aiohttp_session # Import the new close_aiohttp_session

VERIFY_TOKEN = os.getenv("MESSENGER_VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN")

async def keep_alive(request):
    logger.info("Ping from UptimeRobot or test")
    return web.Response(text="Bot alive! No sleep pls~ 😴", status=200)

async def root_handler(request):
    logger.info("Root path accessed.")
    return web.Response(text="Bot is running! Use /keep-alive for health check.", status=200)

async def process_message_async(request, sender_id, query):
    """Xử lý tin nhắn và gửi trả lời một cách bất đồng bộ."""
    try:
        if await is_rate_limited(sender_id):
            reply = "Úi, anh spam quá! Chờ xíu nha~ 😅"
            # Gửi tin nhắn rate limit và kết thúc sớm
            async with request.app['http_session'].post(
                "https://graph.facebook.com/v24.0/me/messages",
                params={'access_token': PAGE_ACCESS_TOKEN},
                json={'recipient': {'id': sender_id}, 'message': {'text': reply}}
            ) as response:
                if response.status == 200:
                    logger.info(f"Sent rate limit message to {sender_id}")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send rate limit message to {sender_id}: {error_text}")
            return

        # Lấy lịch sử và gọi API
        history = await get_user_history_async(sender_id)
        messages = [{"role": "system", "content": get_system_prompt()}] + history + [{"role": "user", "content": query}]
        reply = await run_gemini_api(messages, os.getenv("MODEL_NAME"), sender_id, temperature=0.7, max_tokens=2000)

        # Xử lý thinking block
        thinking_block_pattern = r'<THINKING>(.*?)</THINKING>'
        thinking_match = re.search(thinking_block_pattern, reply, re.DOTALL)
        if thinking_match:
            logger.info(f"--- THINKING DEBUG FOR USER: {sender_id} ---")
            logger.info(thinking_match.group(1).strip())
            logger.info("--- END THINKING DEBUG ---")
            reply = re.sub(thinking_block_pattern, '', reply, flags=re.DOTALL).strip()

        # Xử lý trả lời rỗng hoặc lỗi
        if not reply:
            friendly_errors = [
                "Úi chà! 🥺 Tui bị lỗi đường truyền xíu ròi! Hỏi lại nha!",
                "Ôi không! 😭 Tui đơ mất tiêu, hỏi lại tui nha! ✨",
                "Ái chà chà! 🤯 Mất sóng rồi, thử lại nha anh! 😉"
            ]
            reply = random.choice(friendly_errors)
        
        # Cắt bớt tin nhắn nếu quá dài
        if len(reply) > 2000:
            reply = reply[:1990] + "... (dài quá tui cắt bớt!)"

        # Log lại tin nhắn của bot
        await log_message(sender_id, "assistant", reply)

        # Gửi trả lời cho người dùng
        async with request.app['http_session'].post(
            "https://graph.facebook.com/v24.0/me/messages",
            params={'access_token': PAGE_ACCESS_TOKEN},
            json={'recipient': {'id': sender_id}, 'message': {'text': reply}}
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Messenger API error when replying to {sender_id}: {error_text}")
            else:
                logger.info(f"Sent reply to {sender_id}: {reply}")

    except Exception as e:
        logger.error(f"Error in process_message_async for user {sender_id}: {e}", exc_info=True)
        try:
            # Cố gắng gửi tin nhắn lỗi cho người dùng
            async with request.app['http_session'].post(
                "https://graph.facebook.com/v24.0/me/messages",
                params={'access_token': PAGE_ACCESS_TOKEN},
                json={'recipient': {'id': sender_id}, 'message': {'text': "Ối, tui gặp lỗi rồi, bạn thử lại sau nhé!"}}
            ) as response:
                if response.status == 200:
                    logger.info(f"Sent error notification to {sender_id}")
        except Exception as send_error:
            logger.error(f"Failed to send error notification to {sender_id}: {send_error}")

async def messenger_webhook(request):
    logger.info(f"Received request: {request.method} {request.url}")
    
    # Xác minh webhook cho GET request
    if request.method == 'GET':
        verify_token = request.query.get('hub.verify_token')
        challenge = request.query.get('hub.challenge')
        if verify_token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully.")
            return web.Response(text=challenge, status=200)
        else:
            logger.warning(f"Invalid verify token received: {verify_token}")
            return web.Response(text='Invalid verify token', status=403)
    
    # Xử lý POST request từ Messenger
    if request.method == 'POST':
        try:
            data = await request.json()
            # Log dữ liệu đầy đủ để debug nếu cần, nhưng có thể bỏ qua nếu quá lớn
            # logger.info(f"Webhook data: {json.dumps(data)}")

            if data.get('object') == 'page':
                for entry in data.get('entry', []):
                    for messaging in entry.get('messaging', []):
                        sender_id = messaging.get('sender', {}).get('id')
                        if not sender_id:
                            continue # Bỏ qua nếu không có sender_id

                        # Xử lý tin nhắn văn bản và không phải echo
                        if 'message' in messaging and 'text' in messaging['message'] and not messaging['message'].get('is_echo'):
                            query = messaging['message']['text']
                            logger.info(f"Message from {sender_id}: \"{query}\". Queueing for processing.")
                            
                            # Tạo task chạy nền để xử lý, không block webhook
                            asyncio.create_task(process_message_async(request, sender_id, query))
                        else:
                            # Log các sự kiện khác để dễ dàng theo dõi
                            if 'message' in messaging and messaging['message'].get('is_echo'):
                                logger.info(f"Skipping echo message for {sender_id}.")
                            elif 'delivery' in messaging:
                                logger.info(f"Skipping delivery confirmation for {sender_id}.")
                            elif 'read' in messaging:
                                logger.info(f"Skipping read receipt for {sender_id}.")
                            else:
                                logger.warning(f"Skipping unhandled event for {sender_id}: {messaging}")

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from request body")
        except Exception as e:
            logger.error(f"An unexpected error occurred in webhook handler: {e}", exc_info=True)

        # Luôn trả về 200 OK ngay lập tức để Facebook không gửi lại webhook
        return web.Response(text='OK', status=200)

    # Trả về lỗi nếu phương thức không được hỗ trợ
    return web.Response(text='Method Not Allowed', status=405)
        
async def create_app():
    """Tạo và cấu hình ứng dụng aiohttp."""
    app = web.Application()
    
    # Tạo một ClientSession duy nhất cho toàn bộ ứng dụng
    app['http_session'] = ClientSession()

    app.router.add_get('/', root_handler)
    app.router.add_get('/keep-alive', keep_alive)
    app.router.add_route('*', '/messenger/webhook', messenger_webhook)
    
    # Đảm bảo session và DB connection được đóng khi ứng dụng tắt
    async def on_shutdown(app_instance):
        await app_instance['http_session'].close()
        await close_db_connection()
        await close_aiohttp_session() # Close the aiohttp session from tools.py
    app.on_shutdown.append(on_shutdown)
    
    return app

async def main():
    await init_db() # Khởi tạo DB bất đồng bộ
    app = await create_app()
    port = os.environ.get('PORT')
    if port is None:
        logger.warning("PORT env var not set, using default 10000")
        port = '10000'
    port = int(port)
    logger.info(f"Starting server on port {port}")
    web.run_app(app, host='0.0.0.0', port=port)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ValueError as e:
        logger.error(f"PORT is not a valid number: {e}")
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}")