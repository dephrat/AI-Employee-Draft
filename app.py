import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from db import init_db, get_db, get_setting, save_setting
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
    print("Redirect URI:", url_for("oauth_callback", _external=True))
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
    whitelist = [e.strip() for e in get_setting("whitelist", "").split(",") if e.strip()]
    business_brief = get_setting("business_brief", "")
    emails = get_new_emails(service, whitelist)
    
    results = []
    for email in emails:
        reply = draft_reply(email["body"], email["sender"], email["subject"], business_brief)
        results.append({
            "subject": email["subject"],
            "sender": email["sender"],
            "draft_reply": reply,
            "gmail_id": email["gmail_id"]
        })

    return render_template("dashboard.html", connected=True, emails=results)

@app.route("/send", methods=["POST"])
def send():
    if not session.get("credentials"):
        return redirect(url_for("connect"))

    from gmail import get_gmail_service, send_reply, archive_email

    service = get_gmail_service(session["credentials"])

    to = request.form.get("to")
    subject = request.form.get("subject")
    body = request.form.get("body")
    gmail_id = request.form.get("gmail_id")
    print("gmail_id received:", gmail_id)

    send_reply(service, to, subject, body)
    if gmail_id:
        archive_email(service, gmail_id)

    return redirect(url_for("fetch"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard"))

@app.route("/dismiss", methods=["POST"])
def dismiss():
    if not session.get("credentials"):
        return redirect(url_for("connect"))

    from gmail import get_gmail_service, archive_email

    service = get_gmail_service(session["credentials"])
    gmail_id = request.form.get("gmail_id")

    if gmail_id:
        archive_email(service, gmail_id)

    return redirect(url_for("fetch"))

@app.route("/settings", methods=["GET", "POST"])
def settings():
    saved = False
    if request.method == "POST":
        save_setting("business_brief", request.form.get("business_brief"))
        save_setting("whitelist", request.form.get("whitelist"))
        saved = True
    
    business_brief = get_setting("business_brief", "")
    whitelist = get_setting("whitelist", "")
    return render_template("settings.html", business_brief=business_brief, whitelist=whitelist, saved=saved)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)