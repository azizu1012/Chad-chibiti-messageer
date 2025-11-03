import logging

def setup_logging():
    logger = logging.getLogger('bot_gemini')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.handlers = [file_handler, stream_handler]
    logger.propagate = False

    return logger

logger = setup_logging()