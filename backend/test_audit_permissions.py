from datetime import datetime, timezone
from bson import ObjectId
from pymongo.errors import OperationFailure
from src.mongodb import mongo_db

audit = mongo_db.audit_logs
test_id = ObjectId()

audit.insert_one({
    "_id": test_id,
    "user_id": "permission_test",
    "action": "audit_permission_test",
    "target_id": test_id,
    "timestamp": datetime.now(timezone.utc),
})

print("PASS: Insert allowed")

operations = [
    ("Update", lambda: audit.update_one(
        {"_id": test_id},
        {"$set": {"test_modified": True}},
    )),
    ("Delete", lambda: audit.delete_one(
        {"_id": test_id},
    )),
]

for name, operation in operations:
    try:
        operation()
    except OperationFailure as error:
        message = (error.details or {}).get("errmsg", str(error))

        permission_denied = error.code == 13 or (
            error.code == 8000
            and any(
                text in message.lower()
                for text in [
                    "not authorized",
                    "unauthorized",
                    "not allowed to do action",
                ]
            )
        )

        if permission_denied:
            print(f"PASS: {name} blocked — {message}")
        else:
            print(f"ERROR: {name}, code {error.code} — {message}")
    else:
        print(f"FAIL: {name} was allowed")