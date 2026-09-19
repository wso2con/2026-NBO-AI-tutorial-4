"""Entry point. Run with: python main.py"""

import os

import uvicorn

from agent import app

if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=8000)
