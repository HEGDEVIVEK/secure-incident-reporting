# import os

# from dotenv import load_dotenv
# from pymongo import MongoClient

# load_dotenv()

# MONGO_URI = os.environ["MONGO_URI"]
# MONGO_DB_NAME = os.environ["MONGO_DB_NAME"]

# mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
# mongo_db = mongo_client[MONGO_DB_NAME]

# mongo_client.admin.command("ping")
# print("MongoDB connected successfully")




import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

password_file = os.getenv("MONGO_PASSWORD_FILE")

if password_file:
    # Docker: read the password from a mounted secret file.
    password = Path(password_file).read_text(
        encoding="utf-8-sig"
    ).rstrip("\r\n")
else:
    # Running directly on Windows: use Credential Manager.
    import keyring

    password = keyring.get_password(
        "secure-incident-reporting",
        "atlas-db-password",
    )

if not password:
    raise RuntimeError("MongoDB password is not configured.")

mongo_client = MongoClient(
    f"mongodb+srv://{os.environ['MONGO_HOST']}/",
    username=os.environ["MONGO_USERNAME"],
    password=password,
    authSource="admin",
    serverSelectionTimeoutMS=10000,
)

mongo_db = mongo_client[os.environ["MONGO_DB_NAME"]]

mongo_client.admin.command("ping")
print("MongoDB connected successfully")