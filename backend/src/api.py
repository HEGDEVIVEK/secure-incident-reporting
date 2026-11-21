import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import json
import logging
import traceback
from pathlib import Path

from src.mongodb import mongo_client, mongo_db
from src.schemas import (
    CommentCreate,
    IncidentCreate,
    IncidentStatusUpdate,
    LoginRequest,
    UserCreate,
    ChangePasswordRequest,
    UserAccountUpdate
)
from src.loginLimiter import clear_failures, ensure_not_locked, record_failure
from src.security import password_hasher
from src.verifySession import get_current_user
from src.verifyUser import verify_credentials

# The interactive API docs (/docs, /redoc, /openapi.json) list every endpoint
# and schema, so they are off unless ENABLE_API_DOCS=true is set for local
# development (SR-16, security misconfiguration).
_docs_enabled = os.environ.get("ENABLE_API_DOCS", "").lower() == "true"

app = FastAPI(
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Defensive headers added to every response, including error responses
# (SR-16). The API only returns JSON, so the CSP blocks all content loading.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}

logger = logging.getLogger("incident_reporting")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


def log_request_error(level, event, request, **details):
    # Log the route template, excluding raw URLs and query parameters.
    route = getattr(request.scope.get("route"), "path", "<unmatched>")

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "request_id": request.state.request_id,
        "method": request.method,
        "route": route,
        **details,
    }

    logger.log(level, json.dumps(record))


@app.middleware("http")
async def handle_request_errors(request: Request, call_next):
    # Generate our own reference ID for each request.
    request.state.request_id = secrets.token_hex(16)

    try:
        response = await call_next(request)

    except Exception as exc:
        # Record code locations without exception messages or local values.
        frames = [
            {
                "file": Path(frame.filename).name,
                "line": frame.lineno,
                "function": frame.name,
            }
            for frame in traceback.extract_tb(exc.__traceback__)
        ]

        log_request_error(
            logging.ERROR,
            "unexpected_error",
            request,
            exception_type=type(exc).__name__,
            frames=frames,
        )

        response = JSONResponse(
            status_code=500,
            content={
                "detail": "Something went wrong. Please try again.",
                "request_id": request.state.request_id,
            },
        )

    else:
        # Validation errors are logged by their handler below.
        if response.status_code >= 400 and response.status_code != 422:
            log_request_error(
                logging.WARNING,
                "request_rejected",
                request,
                status_code=response.status_code,
            )

    response.headers["X-Request-ID"] = request.state.request_id
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
):
    log_request_error(
        logging.WARNING,
        "validation_failed",
        request,
        error_count=len(exc.errors()),
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid input. Please check the submitted fields."
        },
    )

    
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/login")
def login(request: LoginRequest, response: Response):
    # Lock the username after repeated failures (ASVS V2.2.1).
    ensure_not_locked(request.username)
    try:
        user = verify_credentials(
            request.username,
            request.password.get_secret_value(),
        )
    except HTTPException:
        record_failure(request.username)
        raise
    clear_failures(request.username)

    # The browser receives the token. MongoDB stores its hash.
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    lifetime = timedelta(minutes=15)

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


@app.get("/me")
def current_account(
    response: Response,
    current_user=Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"

    return {
        "user": {
            "id": str(current_user["_id"]),
            "username": current_user["username"],
            "role": current_user["role"],
        }
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

    # Same lockout as login, so this endpoint cannot be used to guess passwords.
    ensure_not_locked(data.username)
    try:
        user = verify_credentials(data.username, current_password)
    except HTTPException:
        record_failure(data.username)
        raise
    clear_failures(data.username)

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


@app.patch("/users/{user_id}/status-role")
def update_user_account(
    user_id: str,
    data: UserAccountUpdate,
    current_user=Depends(get_current_user),
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=422, detail="Invalid user ID")

    target_id = ObjectId(user_id)

    if target_id == current_user["_id"]:
        raise HTTPException(
            status_code=403,
            detail="You cannot change your own role or account status",
        )

    def update_and_log(session):
        previous = mongo_db.users.find_one_and_update(
            {"_id": target_id},
            {
                "$set": {
                    "role": data.role,
                    "is_active": data.is_active,
                }
            },
            projection={
                "username": 1,
                "role": 1,
                "is_active": 1,
            },
            session=session,
        )

        if previous is None:
            raise HTTPException(status_code=404, detail="User not found")

        role_changed = previous["role"] != data.role
        status_changed = previous["is_active"] != data.is_active

        changes = {}

        if role_changed:
            changes["role"] = {
                "old": previous["role"],
                "new": data.role,
            }

        if status_changed:
            changes["is_active"] = {
                "old": previous["is_active"],
                "new": data.is_active,
            }

            if not data.is_active:
                mongo_db.sessions.delete_many(
                    {"user_id": target_id},
                    session=session,
                )

        if changes:
            mongo_db.audit_logs.insert_one(
                {
                    "user_id": current_user["_id"],
                    "username": current_user["username"],
                    "action": "user_account_updated",
                    "target_type": "user",
                    "target_id": target_id,
                    "target_username": previous["username"],
                    "changes": changes,
                    "timestamp": datetime.now(timezone.utc),
                },
                session=session,
            )

        return {
            "id": str(target_id),
            "username": previous["username"],
            "role": data.role,
            "is_active": data.is_active,
        }

    with mongo_client.start_session() as session:
        return session.with_transaction(update_and_log)


def _to_json_value(value):
    """Convert ObjectIds and datetimes inside an audit entry into JSON-safe values."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _to_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    return value


AUDIT_LOG_FIELDS = (
    "user_id", "username", "action", "target_type", "target_id",
    "target_username", "target_title", "incident_id", "incident_title",
    "old_status", "new_status", "changes", "timestamp",
)


@app.get("/audit-logs")
def list_audit_logs(
    response: Response,
    current_user=Depends(get_current_user),
):
    """Admin reads the newest 200 audit entries (FR-11).

    Read only: the API has no way to edit or delete audit entries (FR-12).
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    response.headers["Cache-Control"] = "no-store"

    entries = (
        mongo_db.audit_logs.find({}, {field: 1 for field in AUDIT_LOG_FIELDS})
        .sort("timestamp", -1)
        .limit(200)
    )

    return [
        {
            "id": str(entry["_id"]),
            **_to_json_value({k: v for k, v in entry.items() if k != "_id"}),
        }
        for entry in entries
    ]


#### USER END POINT ####
@app.post("/add_incidents", status_code=201)
def create_incident(data: IncidentCreate, current_user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)

    incident = {
        "title": data.title,
        "description": data.description,
        "priority": data.priority,
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
            "priority" : 1,
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
            "priority" : incident["priority"],
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
            "priority" : 1,
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
            "priority" : incident["priority"],
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
