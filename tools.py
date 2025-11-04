import asyncio
import requests
import json
import re
import os
from datetime import datetime, timedelta
from config import CITY, WEATHER_API_KEY, WEATHER_CACHE_PATH
from serpapi import GoogleSearch  # SerpAPI (dùng google-search-results package)
from tavily import TavilyClient  # Tavily
import exa_py  # Exa.ai (exa-py package)
from google.generativeai.types import Tool, FunctionDeclaration
from logging_setup import logger
from config import CITY_NAME_MAP  # <-- Đã di chuyển/thêm vào đây
from config import NOTE_PATH
import aiofiles
from config import (
    GOOGLE_CSE_ID,
    GOOGLE_CSE_API_KEY,
    GOOGLE_CSE_ID_1,
    GOOGLE_CSE_API_KEY_1,
    GOOGLE_CSE_ID_2,
    GOOGLE_CSE_API_KEY_2,
    SERPAPI_API_KEY,
    TAVILY_API_KEY,
    EXA_API_KEY,
)
SEARCH_LOCK = asyncio.Lock()
SEARCH_API_COUNTER = 0


weather_lock = asyncio.Lock()
async def get_weather(city_query=None):
    """Lấy thời tiết current + 6 ngày forecast, cache 1 giờ. Luôn trả dict."""
    async with weather_lock:
        # Nếu không truyền city_query thì lấy từ .env
        city_env = CITY or "Ho Chi Minh City"
        city_query = city_query or city_env
        city_en, city_vi = normalize_city_name(city_query)

        # Tạo cache riêng cho từng thành phố
        cache_path = WEATHER_CACHE_PATH.replace(".json", f"_{city_en.replace(' ', '_').lower()}.json")

        # Kiểm tra cache
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cache = json.load(f)
                cache_time = datetime.fromisoformat(cache['timestamp'])
                if datetime.now() - cache_time < timedelta(hours=1):
                    return {**cache['data'], "city_vi": city_vi}  # Trả cache nếu <1h
            except:
                pass

        # Gọi API nếu cache cũ hoặc không có
        if not WEATHER_API_KEY:
            default_data = {
                'current': f'Mưa rào sáng, mây chiều ở {city_vi} (23-28°C).',
                'forecast': [f'Ngày mai: Nắng, 26°C', f'Ngày kia: Mưa, 25°C'] * 3,
                'timestamp': datetime.now().isoformat(),
                'city_vi': city_vi
            }
            with open(cache_path, 'w') as f:
                json.dump({'data': default_data, 'timestamp': datetime.now().isoformat()}, f)
            return default_data

        try:
            url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={city_en}&days=7&aqi=no&alerts=no"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                raise ValueError(f"API status: {response.status_code}")

            data = response.json()
            if 'error' in data:
                raise ValueError(f"API error: {data['error']['message']}")

            current = data['current']['condition']['text'] + f" ({data['current']['temp_c']}°C)"
            forecast = []
            for day in data['forecast']['forecastday'][1:7]:
                forecast.append(f"Ngày {day['date']}: {day['day']['condition']['text']} ({day['day']['avgtemp_c']}°C)")

            weather_data = {
                'current': current,
                'forecast': forecast,
                'timestamp': datetime.now().isoformat(),
                'city_vi': city_vi
            }

            cache_entry = {'data': weather_data, 'timestamp': datetime.now().isoformat()}
            with open(cache_path, 'w') as f:
                json.dump(cache_entry, f, indent=2)

            return weather_data
        except Exception as e:
            logger.error(f"Weather API lỗi: {e}")
            fallback_data = {
                'current': f'Lỗi API, dùng mặc định: Mưa rào ở {city_vi}, 23-28°C.',
                'forecast': [f'Ngày mai: Nắng, 26°C', f'Ngày kia: Mưa, 25°C'] * 3,
                'timestamp': datetime.now().isoformat(),
                'city_vi': city_vi
            }
            with open(cache_path, 'w') as f:
                json.dump({'data': fallback_data, 'timestamp': datetime.now().isoformat()}, f)
            return fallback_data

async def save_note(query):  # Thay def thành async def
    try:
        note = query.lower().replace("ghi note: ", "").replace("save note: ", "").strip()
        async with aiofiles.open(NOTE_PATH, 'a', encoding='utf-8') as f:
            await f.write(f"[{datetime.now().isoformat()}] {note}\n")
        return f"Đã ghi note: {note}"
    except PermissionError:
        return "Lỗi: Không có quyền ghi file notes.txt!"
    except Exception as e:
        return f"Lỗi ghi note: {str(e)}"

# -------------------------------------------------------------------------
# SEARCH API: 3x CSE (Mặc định) HOẶC CSE2 bị thay thế bằng Fallback (theo lệnh AI)
# -------------------------------------------------------------------------
async def run_search_apis(query, mode="general"):
    logger.info(f"CALLING 3x CSE SMART SEARCH for '{query}' (mode: {mode})")
    global SEARCH_API_COUNTER

    # --- [1] Làm sạch & tách query ---
    # Kiểm tra mã khóa ẩn [FORCE FALLBACK] ngay từ đầu
    FORCE_FALLBACK_REQUEST = "[FORCE FALLBACK]" in query.upper()
    
    # Dùng query gốc (hoặc đã làm sạch) để tách sub_queries
    q_base = query.replace("[FORCE FALLBACK]", "").strip()
    
    sub_queries = []
    if " và " in q_base or " and " in q_base.lower() or "," in q_base:
        splitters = re.split(r"\s*(?:và|and|,)\s*", q_base, flags=re.IGNORECASE)
        sub_queries = [q.strip() for q in splitters if q.strip()]
    else:
        sub_queries = [q_base.strip()]

    # --- [2] Mở rộng query thông minh ---
    enriched_queries = []
    for q in sub_queries:
        # Thêm lại logic FORCE_FALLBACK vào query nếu có, để nó được kiểm tra lại ở bước 3
        q_enhanced = (
            f"{q} official update release date patch notes roadmap leaks OR speculation"
        )
        if FORCE_FALLBACK_REQUEST:
             # Nếu AI yêu cầu, thêm tag vào enhanced query
            q_enhanced += " [FORCE FALLBACK]" 
        
        enriched_queries.append(q_enhanced)

    final_results = []

    # --- [3] Chạy từng subquery ---
    for q in enriched_queries:
        async with SEARCH_LOCK:
            # Log chỉ hiện thị query đã được làm sạch để log đẹp hơn
            log_q = q.replace(" [FORCE FALLBACK]", "")
            logger.info(f"Running parallel search for subquery: '{log_q}'")

            # 3 CSE chạy song song
            cse0_task = asyncio.create_task(
                _search_cse(log_q, GOOGLE_CSE_ID, GOOGLE_CSE_API_KEY, 0, start_idx=1)
            )
            cse1_task = asyncio.create_task(
                _search_cse(log_q, GOOGLE_CSE_ID_1, GOOGLE_CSE_API_KEY_1, 1, start_idx=4)
            )
            cse2_task = asyncio.create_task(
                _search_cse(log_q, GOOGLE_CSE_ID_2, GOOGLE_CSE_API_KEY_2, 2, start_idx=7)
            )

            cse0_result, cse1_result, cse2_result = await asyncio.gather(
                cse0_task, cse1_task, cse2_task, return_exceptions=True
            )

            def safe_result(r, name):
                if isinstance(r, Exception):
                    logger.error(f"{name} lỗi: {r}")
                    return ""
                return r or ""

            cse0_result = safe_result(cse0_result, "CSE0")
            cse1_result = safe_result(cse1_result, "CSE1")
            cse2_result = safe_result(cse2_result, "CSE2")

            # --- DÒNG BỔ SUNG: Kiểm tra AI có yêu cầu FORCE FALLBACK hay không ---
            if "[FORCE FALLBACK]" in q.upper() and cse2_result:
                # Logic mới: CSE2 có dữ liệu (không rỗng), nhưng AI đánh giá là RÁC (yêu cầu fallback)
                logger.warning(
                    f"AI yêu cầu [FORCE FALLBACK] → Bỏ qua CSE2 (có dữ liệu rác), chạy Fallback thay thế."
                )
                # Chạy fallback với query đã làm sạch
                cse2_result = await _run_fallback_search(log_q)
                
            # --- Logic cũ: fallback cho CSE2 nếu rỗng ---
            elif not cse2_result:
                logger.warning("CSE2 rỗng/lỗi → fallback qua SerpAPI/Tavily/Exa")
                cse2_result = await _run_fallback_search(log_q)

            # --- Gộp & lọc trùng ---
            parts = [x for x in [cse0_result, cse1_result, cse2_result] if x]
            if parts:
                merged = "\n\n".join(parts)

                # Lọc trùng link (Giữ nguyên)
                unique_lines = []
                seen_links = set()
                for line in merged.splitlines():
                    match = re.search(r"\(Nguồn: (.*?)\)", line)
                    if match:
                        link = match.group(1)
                        if link not in seen_links:
                            seen_links.add(link)
                            unique_lines.append(line)
                    else:
                        unique_lines.append(line)

                final_text = "\n".join(unique_lines)
                final_results.append(
                    f"### 🔍 Kết quả cho truy vấn phụ: {log_q}\n{final_text.strip()}"
                )

    # --- [4] Gộp toàn bộ subquery lại ---
    if final_results:
        logger.info(f"Hoàn tất tìm kiếm {len(final_results)} subquery.")
        return "\n\n".join(final_results)

    logger.error("TẤT CẢ 3 CSE + fallback FAIL.")
    return ""

# -------------------------------------------------------------------------
# CSE ĐỘNG: mỗi CSE có ID/API riêng + offset khác nhau để tránh trùng trang
# -------------------------------------------------------------------------
async def _search_cse(query, cse_id, api_key, index=0, start_idx=1):
    """Tìm kiếm bằng Google CSE cụ thể, có thể chỉnh offset để tránh trùng."""
    if not cse_id or not api_key:
        logger.warning(f"CSE{index} chưa cấu hình ID/API key.")
        return ""

    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": 3,
        "start": start_idx,  # tránh trùng lặp trang kết quả giữa các CSE
        "gl": "vn",
        "hl": "en" if re.search(r"[a-zA-Z]{4,}", query) else "vi",
    }

    try:
        response = await asyncio.to_thread(
            requests.get,
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=10,
        )
        data = response.json()

        if "items" not in data:
            logger.warning(f"CSE{index} không có kết quả hợp lệ cho query '{query[:60]}'")
            return ""

        relevant = []
        for item in data["items"][:3]:
            title = item.get("title", "Không có tiêu đề")
            snippet_raw = item.get("snippet", "")
            snippet = (
                snippet_raw[:330] + "..." if len(snippet_raw) > 130 else snippet_raw
            )
            link = item.get("link", "")
            if any(ad in link.lower() for ad in ["shopee", "lazada", "amazon", "tiki"]):
                continue
            relevant.append(f"**{title}**: {snippet} (Nguồn: {link})")

        if relevant:
            logger.info(f"CSE{index} trả về {len(relevant)} kết quả hợp lệ.")
            return f"**Search CSE{index} (Dynamic):**\n" + "\n".join(relevant) + "\n\n[DÙNG ĐỂ TRẢ LỜI E-GIRL, KHÔNG LEAK NGUỒN]"
        return ""

    except Exception as e:
        logger.error(f"CSE{index} lỗi khi gọi API: {e}")
        return ""


# -------------------------------------------------------------------------
# FALLBACK CHO CSE2
# -------------------------------------------------------------------------
async def _run_fallback_search(query):
    """Fallback xoay vòng SerpAPI / Tavily / Exa nếu CSE2 fail."""
    apis = ["SerpAPI", "Tavily", "Exa"]
    global SEARCH_API_COUNTER
    start_idx = SEARCH_API_COUNTER % 3
    SEARCH_API_COUNTER += 1

    for i in range(3):
        api_name = apis[(start_idx + i) % 3]
        try:
            if api_name == "SerpAPI" and SERPAPI_API_KEY:
                result = await _search_serpapi(query)
            elif api_name == "Tavily" and TAVILY_API_KEY:
                result = await _search_tavily(query)
            elif api_name == "Exa" and EXA_API_KEY:
                result = await _search_exa(query)
            else:
                continue

            if result:
                logger.info(f"Fallback {api_name} thành công cho query '{query[:60]}'")
                return result
            else:
                logger.warning(f"Fallback {api_name} rỗng hoặc lỗi.")
        except Exception as e:
            logger.warning(f"Fallback {api_name} lỗi: {e}")

    logger.error("TẤT CẢ fallback APIs đều thất bại.")
    return ""


async def _search_serpapi(query):
    """SerpAPI: Dùng query của Gemini, tối giản hóa params."""
    if not SERPAPI_API_KEY: return ""
    
    params = {
        "q": query, # Dùng query TỪ GEMINI
        "api_key": SERPAPI_API_KEY,
        "engine": "google",
        "num": 3,
        "gl": "vn",
        "hl": "en" if re.search(r'[a-zA-Z]{4,}', query) else "vi" 
    }
    
    search = GoogleSearch(params)
    results = await asyncio.to_thread(search.get_dict)
    
    if 'organic_results' not in results:
        return ""
    
    # ... (Logic format kết quả giữ nguyên) ...
    relevant = []
    for item in results['organic_results'][:3]:
        title = item.get('title', 'Không có tiêu đề')
        snippet = item.get('snippet', '')[:330] + "..." if len(item.get('snippet', '')) > 130 else item.get('snippet', '')
        link = item.get('link', '')
        if any(ad in link.lower() for ad in ['shopee', 'lazada', 'amazon', 'tiki']): continue
        relevant.append(f"**{title}**: {snippet} (Nguồn: {link})")
    
    return "**Search SerpAPI (Dynamic):**\n" + "\n".join(relevant) + "\n\n[DÙNG ĐỂ TRẢ LỜI E-GIRL, KHÔNG LEAK NGUỒN]" if relevant else ""

async def _search_tavily(query):
    """Tavily: Dùng query của Gemini, client.search() cơ bản."""
    if not TAVILY_API_KEY: return ""
    
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    params = {
        "query": query, # Dùng query TỪ GEMINI
        "search_depth": "basic", 
        "max_results": 3, 
        "include_answer": False
    }
    
    results = await asyncio.to_thread(tavily.search, **params)
    
    if 'results' not in results:
        return ""
    
    # ... (Logic format kết quả giữ nguyên) ...
    relevant = []
    for item in results['results'][:3]:
        title = item.get('title', 'Không có tiêu đề')
        snippet = item.get('content', '')[:330] + "..." if len(item.get('content', '')) > 130 else item.get('content', '')
        link = item.get('url', '')
        if any(ad in link.lower() for ad in ['shopee', 'lazada', 'amazon', 'tiki']): continue
        relevant.append(f"**{title}**: {snippet} (Nguồn: {link})")
    
    return "**Search Tavily (Dynamic):**\n" + "\n".join(relevant) + "\n\n[DÙNG ĐỂ TRẢ LỜI E-GIRL, KHÔNG LEAK NGUỒN]" if relevant else ""

async def _search_exa(query):
    """Exa.ai: Dùng query của Gemini, tìm kiếm neural search cơ bản."""
    if not EXA_API_KEY: return ""
    
    exa = exa_py.Exa(api_key=EXA_API_KEY)
    params = {
        "query": query, # Dùng query TỪ GEMINI
        "num_results": 3, 
        "use_autoprompt": True, 
        "type": "neural" # Neural search là chế độ mạnh nhất của Exa
    }
    
    results = await asyncio.to_thread(exa.search, **params)
    
    if not results.results:
        return ""
    
    # ... (Logic format kết quả giữ nguyên) ...
    relevant = []
    for item in results.results[:3]:
        title = item.title or 'Không có tiêu đề'
        snippet = item.text[:330] + "..." if len(item.text or '') > 130 else item.text or ''
        link = item.url
        if any(ad in link.lower() for ad in ['shopee', 'lazada', 'amazon', 'tiki']): continue
        relevant.append(f"**{title}**: {snippet} (Nguồn: {link})")
    
    return "**Search Exa.ai (Dynamic):**\n" + "\n".join(relevant) + "\n\n[DÙNG ĐỂ TRẢ LỜI E-GIRL, KHÔNG LEAK NGUỒN]" if relevant else ""

def run_calculator(equation):
    try:
        # Rất nguy hiểm, chỉ dùng nếu bạn kiểm soát input rất chặt
        # Giả định có thư viện toán học an toàn ở đây
        import math
        return eval(equation, {"__builtins__": None}, math.__dict__)
    except Exception as e:
        return f"Calculation error: {str(e)}"

ALL_TOOLS = [
    Tool(function_declarations=[
        FunctionDeclaration(
            name="web_search",
            description=(
                "Tìm kiếm thông tin cập nhật (tin tức, giá cả, phiên bản game, sự kiện) sau năm 2024. "
                "Chỉ dùng khi kiến thức nội bộ của bạn đã lỗi thời so với ngày hiện tại. "
                "Yêu cầu TỰ DỊCH câu hỏi tiếng Việt của user thành một query tìm kiếm tiếng Anh TỐI ƯU."
            ),
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Câu hỏi bằng tiếng Anh"}},
                "required": ["query"]
            }
        )
    ]),
    Tool(function_declarations=[
        FunctionDeclaration(
            name="get_weather",
            description="Lấy thông tin thời tiết hiện tại cho một thành phố cụ thể.",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string", "description": "Tên thành phố, ví dụ: 'Hanoi', 'Tokyo'."}},
                "required": ["city"]
            }
        )
    ]),
    Tool(function_declarations=[
        FunctionDeclaration(
            name="calculate",
            description="Giải các bài toán số học hoặc biểu thức phức tạp, bao gồm các hàm lượng giác, logarit, và đại số.",
            parameters={
                "type": "object",
                "properties": {"equation": {"type": "string", "description": "Biểu thức toán học dưới dạng string, ví dụ: 'sin(pi/2) + 2*x'."}},
                "required": ["equation"]
            }
        )
    ]),
    Tool(function_declarations=[
        FunctionDeclaration(
            name="save_note",
            description="Lưu một mẩu thông tin, ghi chú hoặc lời nhắc cụ thể theo yêu cầu của người dùng để bạn có thể truy cập lại sau.",
            parameters={
                "type": "object",
                "properties": {"note": {"type": "string", "description": "Nội dung ghi chú cần lưu."}},
                "required": ["note"]
            }
        )
    ]),
]

async def call_tool(function_call, user_id):
    name = function_call.name
    args = dict(function_call.args)
    logger.info(f"TOOL GỌI: {name} | Args: {args} | User: {user_id}")

    try:
        if name == "web_search":
            query = args.get("query", "")
            return await run_search_apis(query, "general")  # Giả định hàm này trong code gốc, anh add nếu cần

        elif name == "get_weather":
            city = args.get("city", "Ho Chi Minh City")
            data = await get_weather(city)
            return json.dumps(data, ensure_ascii=False, indent=2)

        elif name == "calculate":
            eq = args.get("equation", "")
            return await asyncio.to_thread(run_calculator, eq)

        elif name == "save_note":
            note = args.get("note", "")
            return await save_note(note, user_id)

        else:
            return "Tool không tồn tại!"

    except Exception as e:
        logger.error(f"Tool {name} lỗi: {e}")
        return f"Lỗi tool: {str(e)}"

def normalize_city_name(city_query):
    # from config import CITY_NAME_MAP # đã được di chuyển lên trên
    if not city_query:
        return ("Ho Chi Minh City", "Thành phố Hồ Chí Minh")
    city_key = city_query.strip().lower()
    for k, v in CITY_NAME_MAP.items():
        if k in city_key:
            return v
    return (city_query, city_query.title())