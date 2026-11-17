"""VinDelivery web server (runs on EC2): serves the pages, signs staff in with Cognito,
verifies their token, and forwards every request to the Lambda backend.

Env (written to /etc/vindelivery.env by Terraform): AWS_REGION, COGNITO_USER_POOL_ID,
COGNITO_CLIENT_ID, LAMBDA_FUNCTION_NAME. Run: python3 -m gunicorn --bind 0.0.0.0:80 server:app
"""
import json
import logging
import os

import boto3
import jwt
from botocore.exceptions import ClientError
from flask import Flask, jsonify, request, send_from_directory

REGION = os.environ["AWS_REGION"]
POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
FUNCTION = os.environ["LAMBDA_FUNCTION_NAME"]
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}"
HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = {"": "staff.html", "staff.html": "staff.html", "admin": "admin.html", "admin.html": "admin.html",
         "app.js": "app.js", "app.css": "app.css"}

app = Flask(__name__, static_folder=None)
log = logging.getLogger("vindelivery")
cognito = boto3.client("cognito-idp", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
jwks = jwt.PyJWKClient(f"{ISSUER}/.well-known/jwks.json")

PASSWORD_RULE = "Use at least 12 characters with upper and lower case letters, a number and a symbol."


def fail(status, message):
    return {"ok": False, "status": status, "error": {"message": message}}


def reply(result):
    return jsonify(result), result.get("status", 200)


def invoke(event):
    try:
        resp = lam.invoke(FunctionName=FUNCTION, Payload=json.dumps(event).encode())
        if resp.get("FunctionError"):
            raise RuntimeError(resp["Payload"].read())
        return json.loads(resp["Payload"].read())
    except Exception:
        log.exception("Lambda invoke failed")
        return fail(502, "The service is unavailable. Try again shortly.")


def verify(token):
    """Return {'username', 'groups'} for a valid Cognito access token, else None."""
    try:
        key = jwt.PyJWKClient.get_signing_key_from_jwt(jwks, token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], issuer=ISSUER, options={"verify_aud": False})
    except Exception:
        return None
    if claims.get("token_use") != "access" or claims.get("client_id") != CLIENT_ID:
        return None
    return {"username": claims["username"], "groups": claims.get("cognito:groups", [])}


def signed_in(auth_result):
    token = auth_result["AccessToken"]
    user = verify(token)
    if not user:
        return fail(401, "Sign in failed. Try again.")
    return {"ok": True, "status": 200, "data": {"token": token, **user}}


def call(action, payload=None):
    header = request.headers.get("Authorization", "")
    user = verify(header[7:]) if header.startswith("Bearer ") else None
    if not user:
        return reply(fail(401, "Your session expired. Sign in again."))
    return reply(invoke({"action": action, "device_id": request.headers.get("X-Device-Id", ""),
                         "user": user, "payload": payload or {}}))


# Pages
@app.get("/", defaults={"name": ""})
@app.get("/<name>")
def page(name):
    if name not in PAGES:
        return "Not found", 404
    return send_from_directory(HERE, PAGES[name])


@app.get("/healthz")
def health():
    return "ok"


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com")
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# Sign in
@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    username, password = str(body.get("username", "")).strip(), str(body.get("password", ""))
    try:
        resp = cognito.initiate_auth(ClientId=CLIENT_ID, AuthFlow="USER_PASSWORD_AUTH",
                                     AuthParameters={"USERNAME": username, "PASSWORD": password})
    except ClientError as err:
        code = err.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            result = invoke({"action": "report_failed_login", "username": username})
            if result.get("status") == 423:
                return reply(fail(423, "Access restricted. Contact an administrator."))
            return reply(fail(401, "Incorrect username or password."))
        log.exception("Cognito login error")
        return reply(fail(503, "Sign in is unavailable. Try again shortly."))

    if resp.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
        return reply({"ok": True, "status": 200, "data": {
            "challenge": "NEW_PASSWORD_REQUIRED", "session": resp["Session"], "username": username}})
    if "AuthenticationResult" not in resp:
        return reply(fail(403, "This account needs an administrator before it can sign in."))
    return reply(signed_in(resp["AuthenticationResult"]))


@app.post("/api/new-password")
def new_password():
    body = request.get_json(silent=True) or {}
    try:
        resp = cognito.respond_to_auth_challenge(
            ClientId=CLIENT_ID, ChallengeName="NEW_PASSWORD_REQUIRED", Session=str(body.get("session", "")),
            ChallengeResponses={"USERNAME": str(body.get("username", "")),
                                "NEW_PASSWORD": str(body.get("password", ""))})
    except ClientError as err:
        code = err.response["Error"]["Code"]
        if code in ("InvalidPasswordException", "InvalidParameterException"):
            return reply(fail(400, PASSWORD_RULE))
        if code in ("NotAuthorizedException", "ExpiredCodeException", "CodeMismatchException"):
            return reply(fail(401, "That request expired. Sign in again."))
        log.exception("Cognito challenge error")
        return reply(fail(503, "Sign in is unavailable. Try again shortly."))
    if "AuthenticationResult" not in resp:
        return reply(fail(403, "This account needs an administrator before it can sign in."))
    return reply(signed_in(resp["AuthenticationResult"]))


# API
@app.get("/api/items")
def list_items():
    return call("list_items", {"page": request.args.get("page", 1), "page_size": request.args.get("page_size", 50)})


@app.get("/api/items/<path:item_id>")
def find_item(item_id):
    action = "find_item_binary" if request.args.get("method") == "binary" else "find_item"
    return call(action, {"item_id": item_id})


@app.get("/api/search")
def search_name():
    return call("search_name", {"name": request.args.get("name", "")})


@app.post("/api/items")
def store_item():
    return call("store_item", request.get_json(silent=True) or {})


@app.delete("/api/items/<path:item_id>")
def delete_item(item_id):
    return call("delete_item", {"item_id": item_id})
