import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from db import init_db, get_db
from gmail import get_oauth_flow, credentials_to_dict

load_dotenv()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

@app.route("/")
def dashboard():
    connected = session.get("credentials") is not None
    return render_template("dashboard.html", connected=connected)

@app.route("/connect")
def connect():
    flow = get_oauth_flow(url_for("oauth_callback", _external=True))
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )
    session["state"] = state
    session["code_verifier"] = flow.code_verifier
    return redirect(auth_url)

@app.route("/oauth/callback")
def oauth_callback():
    flow = get_oauth_flow(url_for("oauth_callback", _external=True))
    flow.code_verifier = session.get("code_verifier")
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = credentials_to_dict(credentials)
    return redirect(url_for("dashboard"))

@app.route("/fetch")
def fetch():
    if not session.get("credentials"):
        return redirect(url_for("connect"))

    from gmail import get_gmail_service, get_new_emails
    from ai import draft_reply

    service = get_gmail_service(session["credentials"])
    whitelist = ["notifications-noreply@linkedin.com"]
    emails = get_new_emails(service, whitelist)

    business_brief = "We are a small consulting firm called Exemplar Consulting Inc. The owner's name is Daniel Ephrat. We respond professionally and concisely."

    results = []
    for email in emails[:2]:
        reply = draft_reply(email["body"], email["sender"], email["subject"], business_brief)
        results.append({
            "subject": email["subject"],
            "sender": email["sender"],
            "draft_reply": reply
        })

    return render_template("dashboard.html", connected=True, emails=results)

@app.route("/send", methods=["POST"])
def send():
    if not session.get("credentials"):
        return redirect(url_for("connect"))

    from gmail import get_gmail_service, send_reply

    service = get_gmail_service(session["credentials"])

    to = request.form.get("to")
    subject = request.form.get("subject")
    body = request.form.get("body")

    send_reply(service, to, subject, body)
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)