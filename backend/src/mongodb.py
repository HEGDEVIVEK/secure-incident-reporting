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

import keyring
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

password = keyring.get_password("secure-incident-reporting", "atlas-db-password")
if not password:
    raise RuntimeError(
        "Atlas password was not found in the OS credential store "
        "(Windows Credential Manager, macOS Keychain, or Linux Secret Service). "
        "Store it once with: python -c \"import keyring, getpass; "
        "keyring.set_password('secure-incident-reporting', 'atlas-db-password', getpass.getpass())\""
    )

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