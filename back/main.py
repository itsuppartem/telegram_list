import logging

import uvicorn
from fastapi import FastAPI

from config import HOST, PORT
from routes import router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()])

app = FastAPI(title="Shopping List API", description="API для управления списками покупок", version="1.0.0")

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
