import asyncio
import re
import json
import random
from datetime import datetime
from google.generativeai import GenerativeModel
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from config import GEMINI_API_KEYS, MODEL_NAME
from logging_setup import logger
from tools import ALL_TOOLS, call_tool
from database import log_message

# System prompt mới (đã adjust cho Teams)
system_prompt = (  # Như trên, paste ở phần 1
    # ... (full prompt ở trên)
)

async def run_gemini_api(messages, model_name, user_id, temperature=0.7, max_tokens=2000):
    keys = GEMINI_API_KEYS
    if not keys:
        return "Lỗi: Không có API key."
    
    gemini_messages = []
    system_instruction = None
    for msg in messages:
        if msg["role"] == "system":
            system_instruction = msg["content"]
            continue
           
        if "content" in msg and isinstance(msg["content"], str):
            role = "model" if msg["role"] == "assistant" else msg["role"]
            gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})
       
        elif "parts" in msg:
            role = "model" if msg["role"] == "assistant" else msg["role"]
            gemini_messages.append({"role": role, "parts": msg["parts"]})
    
    for i, api_key in enumerate(keys):
        logger.info(f"THỬ KEY {i+1}: {api_key[:8]}...")
        try:
            genai.configure(api_key=api_key)
           
            model = GenerativeModel(
                model_name,
                tools=ALL_TOOLS,
                system_instruction=system_instruction,
                safety_settings=[
                    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
                    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                ],
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
            )
            
            response = model.generate_content(gemini_messages)
            
            reply = ""
            for part in response.parts:
                if "text" in part:
                    reply += part["text"]
                elif "function_call" in part:
                    function_call = part["function_call"]
                    tool_result = await call_tool(function_call, user_id)
                    # Thêm tool response vào lịch sử và regenerate
                    gemini_messages.append({"role": "model", "parts": [part]})
                    gemini_messages.append({"role": "user", "parts": [{"function_response": {"name": function_call.name, "response": tool_result}}]})
                    return await run_gemini_api(messages, model_name, user_id, temperature, max_tokens)  # Recursive với tool response
            
            return reply
        
        except Exception as e:
            logger.error(f"Key {i+1} lỗi: {e}")
            if i == len(keys) - 1:
                return f"Lỗi: Tất cả keys thất bại - {str(e)}"