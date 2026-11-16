import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.mongodb import mongo_client, mongo_db
from src.schemas import (
    CommentCreate,
    IncidentCreate,
    IncidentStatusUpdate,
    LoginRequest,
    UserCreate,
    UserRoleUpdate,
    UserStatusUpdate,
    ChangePasswordRequest
)
from src.security import password_hasher
from src.verifySession import get_current_user
from src.verifyUser import verify_credentials

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid input. Please check the submitted fields."},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/login")
def login(request: LoginRequest, response: Response):
    user = verify_credentials(
        request.username,
        request.password.get_secret_value(),
    )

    # The browser receives the token. MongoDB stores its hash.
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    lifetime = timedelta(minutes=30)

    mongo_db.sessions.insert_one(
        {
            "_id": token_hash,
            "user_id": user["_id"],
            "username": user["username"],
            "expires_at": datetime.now(timezone.utc) + lifetime,
        }
    )

    response.set_cookie(
        key="session_token",
        value=token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return {
        "message": "Signed in",
        "user": {
            "id": str(user["_id"]), 
            "role": user["role"],
            "username": user["username"],          
            },
    }


@app.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")

    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        mongo_db.sessions.delete_one({"_id": token_hash})

    response.delete_cookie(
        key="session_token",
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    return {"message": "Signed out"}


@app.post("/update-password")
def update_password(data: ChangePasswordRequest):
    current_password = data.current_password.get_secret_value()
    new_password = data.new_password.get_secret_value()

    user = verify_credentials(data.username, current_password)

    if new_password == current_password:
        raise HTTPException(
            status_code=422,
            detail="Choose a password different from your current password.",
        )

    new_hash = password_hasher.hash(new_password)

    def change_password_and_log(db_session):
        # Only update if the account is still active and the verified hash still matches.
        result = mongo_db.users.update_one(
            {
                "_id": user["_id"],
                "is_active": True,
                "password_hash": user["password_hash"],
            },
            {"$set": {"password_hash": new_hash}},
            session=db_session,
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password",
            )

        mongo_db.sessions.delete_many(
            {"user_id": user["_id"]},
            session=db_session,
        )

        mongo_db.audit_logs.insert_one(
            {
                "user_id": user["_id"],
                "username": user["username"],
                "action": "password_changed",
                "target_type": "user",
                "target_id": user["_id"],
                "target_username": user["username"],
                "timestamp": datetime.now(timezone.utc),
            },
            session=db_session,
        )

    with mongo_client.start_session() as db_session:
        db_session.with_transaction(change_password_and_log)

    return {"message": "Password updated. Log in with your new password."}


#### ADMIN END POINTS ####
@app.post("/add_users", status_code=201)
def create_user(data: UserCreate, current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    account = {
        "username": data.username,
        "password_hash": password_hasher.hash(data.password.get_secret_value()),
        "role": data.role,
        "is_active": True,
    }

    try:
        with mongo_client.start_session() as session:
            with session.start_transaction():
                result = mongo_db.users.insert_one(account, session=session)

                mongo_db.audit_logs.insert_one(
                    {
                        "user_id": current_user["_id"],
                        "username": current_user["username"],
                        "action": "user_created",
                        "target_type": "user",
                        "target_id": result.inserted_id,
                        "target_username": data.username,
                        "timestamp": datetime.now(timezone.utc),
                    },
                    session=session,
                )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Username already exists")

    return {"id": str(result.inserted_id), "username": data.username}


@app.get("/list_users")
def list_users(current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    users = mongo_db.users.find(
        {},
        {"username": 1, "role": 1, "is_active": 1},
    ).sort("username", 1)

    return [
        {
            "id": str(user["_id"]),
            "username": user["username"],
            "role": user["role"],
            "is_active": user["is_active"],
        }
        for user in users
    ]


@app.patch("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    data: UserRoleUpdate,
    current_user=Depends(get_current_user),
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=422, detail="Invalid user ID")

    target_id = ObjectId(user_id)
    if target_id == current_user["_id"]:
        raise HTTPException(status_code=403, detail="You cannot change your own role")

    def update_and_log(session):
        previous = mongo_db.users.find_one_and_update(
            {"_id": target_id},
            {"$set": {"role": data.role}},
            projection={"username": 1, "role": 1},
            session=session,
        )

        if previous is None:
            raise HTTPException(status_code=404, detail="User not found")

        if previous["role"] != data.role:
            mongo_db.audit_logs.insert_one(
                {
                    "user_id": current_user["_id"],
                    "username": current_user["username"],
                    "action": "user_role_changed",
                    "target_type": "user",
                    "target_id": target_id,
                    "target_username": previous["username"],
                    "old_role": previous["role"],
                    "new_role": data.role,
                    "timestamp": datetime.now(timezone.utc),
                },
                session=session,
            )

        return {"id": str(target_id), "username": previous["username"], "role": data.role}

    with mongo_client.start_session() as session:
        return session.with_transaction(update_and_log)


@app.patch("/users/{user_id}/status")
def update_user_status(
    user_id: str,
    data: UserStatusUpdate,
    current_user=Depends(get_current_user),
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=422, detail="Invalid user ID")

    target_id = ObjectId(user_id)

    if target_id == current_user["_id"] and not data.is_active:
        raise HTTPException(status_code=403, detail="You cannot deactivate your own account")

    def update_and_log(session):
        previous = mongo_db.users.find_one_and_update(
            {"_id": target_id},
            {"$set": {"is_active": data.is_active}},
            projection={"username": 1, "is_active": 1},
            session=session,
        )

        if previous is None:
            raise HTTPException(status_code=404, detail="User not found")

        if previous["is_active"] != data.is_active:
            if not data.is_active:
                mongo_db.sessions.delete_many({"user_id": target_id}, session=session)

            mongo_db.audit_logs.insert_one(
                {
                    "user_id": current_user["_id"],
                    "username": current_user["username"],
                    "action": "user_activated" if data.is_active else "user_deactivated",
                    "target_type": "user",
                    "target_id": target_id,
                    "target_username": previous["username"],
                    "timestamp": datetime.now(timezone.utc),
                },
                session=session,
            )

        return {
            "id": str(target_id),
            "username": previous["username"],
            "is_active": data.is_active,
        }

    with mongo_client.start_session() as session:
        return session.with_transaction(update_and_log)




#### USER END POINT ####
@app.post("/add_incidents", status_code=201)
def create_incident(data: IncidentCreate, current_user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)

    incident = {
        "title": data.title,
        "description": data.description,
        "status": "open",
        "submitted_by_id": current_user["_id"],
        "submitted_by_name": current_user["username"],
        "created_at": now,
    }

    with mongo_client.start_session() as session:
        with session.start_transaction():
            result = mongo_db.incidents.insert_one(incident, session=session)

            mongo_db.audit_logs.insert_one(
                {
                    "user_id": current_user["_id"],
                    "username": current_user["username"],
                    "action": "incident_created",
                    "target_type": "incident",
                    "target_id": result.inserted_id,
                    "target_title": data.title,
                    "timestamp": now,
                },
                session=session,
            )

    return {"id": str(result.inserted_id), "status": "open"}


@app.get("/incidents/mine")
def list_my_incidents(current_user=Depends(get_current_user)):
    incidents = mongo_db.incidents.find(
        {"submitted_by_id": current_user["_id"]},
        {
            "title": 1,
            "description": 1,
            "status": 1,
            "created_at": 1,
            "comments": 1,
        },
    ).sort("created_at", -1)

    return [
        {
            "id": str(incident["_id"]),
            "title": incident["title"],
            "description": incident["description"],
            "status": incident["status"],
            "created_at": incident["created_at"],
            "comments": [
                {
                    "id": str(comment["_id"]),
                    "text": comment["text"],
                    "username": comment["username"],
                    "created_at": comment["created_at"],
                }
                for comment in incident.get("comments", [])
            ],
        }
        for incident in incidents
    ]




#### REVIEWER and ADMIN END POINT ####
def fetch_incidents(query):
    """Return matching incidents, newest first, with IDs formatted for JSON."""
    incidents = mongo_db.incidents.find(
        query,
        {
            "title": 1,
            "description": 1,
            "status": 1,
            "submitted_by_name": 1,
            "created_at": 1,
            "comments": 1,
        },
    ).sort("created_at", -1)

    return [
        {
            "id": str(incident["_id"]),
            "title": incident["title"],
            "description": incident["description"],
            "status": incident["status"],
            "submitted_by_name": incident.get("submitted_by_name"),
            "created_at": incident["created_at"],
            "comments": [
                {
                    "id": str(comment["_id"]),
                    "username": comment["username"],
                    "text": comment["text"],
                    "created_at": comment.get("created_at"),
                }
                for comment in incident.get("comments", [])
            ],
        }
        for incident in incidents
    ]

@app.get("/incidents")
def list_all_incidents(current_user=Depends(get_current_user)):
    if current_user["role"] not in ("admin", "reviewer"):
        raise HTTPException(status_code=403, detail="Reviewer or admin access required")

    return fetch_incidents({})


@app.post("/incidents/{incident_id}/comments", status_code=201)
def add_comment(
    incident_id: str,
    data: CommentCreate,
    current_user=Depends(get_current_user),
):
    if current_user["role"] not in ("reviewer", "admin"):
        raise HTTPException(status_code=403, detail="Reviewer or admin access required")

    if not ObjectId.is_valid(incident_id):
        raise HTTPException(status_code=422, detail="Invalid incident ID")

    incident_object_id = ObjectId(incident_id)
    now = datetime.now(timezone.utc)

    comment = {
        "_id": ObjectId(),
        "text": data.text,
        "user_id": current_user["_id"],
        "username": current_user["username"],
        "created_at": now,
    }

    def save_comment_and_log(session):
        incident = mongo_db.incidents.find_one_and_update(
            {"_id": incident_object_id},
            {"$push": {"comments": comment}},
            projection={"title": 1},
            session=session,
        )

        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        mongo_db.audit_logs.insert_one(
            {
                "user_id": current_user["_id"],
                "username": current_user["username"],
                "action": "comment_created",
                "target_type": "comment",
                "target_id": comment["_id"],
                "incident_id": incident_object_id,
                "incident_title": incident["title"],
                "timestamp": now,
            },
            session=session,
        )

    with mongo_client.start_session() as session:
        session.with_transaction(save_comment_and_log)

    return {"id": str(comment["_id"]), "incident_id": incident_id}



#### REVIEWER END POINT ####
@app.patch("/incidents/{incident_id}/status")
def update_incident_status(
    incident_id: str,
    data: IncidentStatusUpdate,
    current_user=Depends(get_current_user),
):
    if current_user["role"] != "reviewer":
        raise HTTPException(status_code=403, detail="Reviewer access required")

    if not ObjectId.is_valid(incident_id):
        raise HTTPException(status_code=422, detail="Invalid incident ID")

    def update_and_log(session):
        # The original document supplies the old status for the audit entry.
        previous = mongo_db.incidents.find_one_and_update(
            {"_id": ObjectId(incident_id)},
            {"$set": {"status": data.status}},
            projection={"title": 1, "status": 1},
            session=session,
        )

        if previous is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        if previous["status"] != data.status:
            mongo_db.audit_logs.insert_one(
                {
                    "user_id": current_user["_id"],
                    "username": current_user["username"],
                    "action": "incident_status_changed",
                    "target_type": "incident",
                    "target_id": previous["_id"],
                    "target_title": previous["title"],
                    "old_status": previous["status"],
                    "new_status": data.status,
                    "timestamp": datetime.now(timezone.utc),
                },
                session=session,
            )

    with mongo_client.start_session() as session:
        session.with_transaction(update_and_log)

    return {"id": incident_id, "status": data.status}
