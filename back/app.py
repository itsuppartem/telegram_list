import logging

import uvicorn
from fastapi import FastAPI

from config import HOST, PORT
from routes import router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
