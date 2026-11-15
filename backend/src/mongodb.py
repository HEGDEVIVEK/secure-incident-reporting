import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB_NAME = os.environ["MONGO_DB_NAME"]

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
mongo_db = mongo_client[MONGO_DB_NAME]

mongo_client.admin.command("ping")
print("MongoDB connected successfully")