import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import os
from urllib.parse import urlsplit
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
from src.security import password_hasher
from src.verifySession import get_current_user
from src.verifyUser import verify_credentials

TRUSTED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,https://secure-incident-report.duckdns.org",
    ).split(",")
    if origin.strip()
}

def get_referer_origin(referer):
    try:
        parsed = urlsplit(referer)
        if parsed.scheme not in ("http", "https"):
            return None
        return f"{parsed.scheme}://{parsed.netloc}"
    except ValueError:
        return None

app = FastAPI(
    docs_url=None, 
    redoc_url=None, 
    openapi_url=None
    )

# Security headers added to every API response (SR-16: security misconfiguration)
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",  # incident data is sensitive, so don't let browsers cache it
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
async def csrf_protection(request: Request, call_next):

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:

        origin = request.headers.get("Origin")

        if origin is None:
            referer = request.headers.get("Referer")
            origin = get_referer_origin(referer) if referer else None

        if origin not in TRUSTED_ORIGINS:
            return JSONResponse(
                status_code=403,
                content={"detail": "Untrusted request origin"},
            )

    return await call_next(request)
    

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
    response.headers.update(SECURITY_HEADERS)
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
    user = verify_credentials(
        request.username,
        request.password.get_secret_value(),
    )

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


#### USER END POINT ####
@app.post("/add_incidents", status_code=201)
def create_incident(data: IncidentCreate, current_user=Depends(get_current_user)):

    if current_user["role"] != "user":
        raise HTTPException(status_code=403, detail="User access required")

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
    if current_user["role"] != "user":
        raise HTTPException(status_code=403, detail="User access required")

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
