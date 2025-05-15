import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, BACKEND_URL
from handlers import Handlers
from utils import BotUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)


class Bot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.bot_utils = BotUtils(self.bot, BACKEND_URL)
        self.dp = Dispatcher()
        self.handlers = Handlers(self.bot_utils)
        self.dp.include_router(self.handlers.router)

    async def launch_bot(self):
        try:
            await self.bot.delete_webhook(drop_pending_updates=True)
            await self.dp.start_polling(self.bot, allowed_updates=self.dp.resolve_used_update_types())
        except Exception as e:
            logger.exception("Ошибка при запуске бота:")
            raise
        finally:
            await self.bot_utils.close_client()
