import asyncio

from bot import Bot

if __name__ == '__main__':
    bot_instance = Bot()
    try:
        asyncio.run(bot_instance.launch_bot())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен!")
