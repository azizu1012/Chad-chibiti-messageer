import asyncio
import json
from google.generativeai.types import Tool, FunctionDeclaration
from config import logger
from .gemini_api import run_calculator  # Import nếu có (giả định trong gemini_api)
# Giả định get_weather, save_note từ code gốc, anh adjust nếu cần
async def get_weather(city):
    # Code gốc get_weather ở đây
    pass

async def save_note(note, user_id):
    # Code gốc save_note ở đây
    pass

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
    from config import CITY_NAME_MAP  # Import nếu cần
    if not city_query:
        return ("Ho Chi Minh City", "Thành phố Hồ Chí Minh")
    city_key = city_query.strip().lower()
    for k, v in CITY_NAME_MAP.items():
        if k in city_key:
            return v
    return (city_query, city_query.title())