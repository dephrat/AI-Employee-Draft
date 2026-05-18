import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from gmail import get_oauth_flow, credentials_to_dict
from concurrent.futures import ThreadPoolExecutor
from google.auth.exceptions import RefreshError
from db import init_db, get_db, get_setting, save_setting, delete_draft

load_dotenv()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

def current_account():
    return session.get("account_email")

@app.errorhandler(RefreshError)
def handle_refresh_error(e):
    session.clear()
    return redirect(url_for("dashboard"))

@app.route("/")
def dashboard():
    connected = session.get("credentials") is not None
    owner_name = get_setting("owner_name", "", current_account())
    return render_template("dashboard.html", connected=connected, owner_name=owner_name)

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
    
    from gmail import get_gmail_service, get_account_email
    service = get_gmail_service(session["credentials"])
    session["account_email"] = get_account_email(service)
    
    return redirect(url_for("dashboard"))

@app.route("/fetch")
def fetch():
    if not session.get("credentials"):
        return redirect(url_for("connect"))

    from gmail import get_gmail_service, get_new_emails
    from ai import draft_reply
    from db import get_draft, save_draft

    service = get_gmail_service(session["credentials"])
    whitelist = [e.strip() for e in get_setting("whitelist", "", current_account()).split(",") if e.strip()]
    business_brief = get_setting("business_brief", "", current_account())
    emails = get_new_emails(service, whitelist)

    def process_email(email):
        existing = get_draft(email["gmail_id"])
        if existing:
            return {
                "subject": existing["subject"],
                "sender": existing["sender"],
                "draft_reply": existing["draft_reply"],
                "gmail_id": existing["gmail_id"],
                "body": existing["body"]
            }
        reply = draft_reply(email["body"], email["sender"], email["subject"], business_brief)
        save_draft(email["gmail_id"], email["sender"], email["subject"], email["body"], reply)
        return {
            "subject": email["subject"],
            "sender": email["sender"],
            "draft_reply": reply,
            "gmail_id": email["gmail_id"],
            "body": email["body"]
        }

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(process_email, emails))

    session["drafted_emails"] = results
    return render_template("dashboard.html", connected=True, emails=results, owner_name=get_setting("owner_name", "", current_account()))

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

    send_reply(service, to, subject, body)
    if gmail_id:
        archive_email(service, gmail_id)
        delete_draft(gmail_id)

    emails = session.get("drafted_emails", [])
    emails = [e for e in emails if e["gmail_id"] != gmail_id]
    session["drafted_emails"] = emails

    return render_template("dashboard.html", connected=True, emails=emails, owner_name=get_setting("owner_name", "", current_account()))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard"))

@app.route("/dismiss", methods=["POST"])
def dismiss():
    if not session.get("credentials"):
        return redirect(url_for("connect"))

    from gmail import get_gmail_service, label_email

    service = get_gmail_service(session["credentials"])
    gmail_id = request.form.get("gmail_id")

    if gmail_id:
        label_email(service, gmail_id, "ai-employee-review")
        delete_draft(gmail_id)

    emails = session.get("drafted_emails", [])
    emails = [e for e in emails if e["gmail_id"] != gmail_id]
    session["drafted_emails"] = emails

    return render_template("dashboard.html", connected=True, emails=emails, owner_name=get_setting("owner_name", "", current_account()))

@app.route("/settings", methods=["GET", "POST"])
def settings():
    saved = False
    account = current_account()
    if request.method == "POST":
        save_setting("owner_name", request.form.get("owner_name"), account)
        save_setting("business_brief", request.form.get("business_brief"), account)
        save_setting("whitelist", request.form.get("whitelist"), account)
        saved = True
    
    owner_name = get_setting("owner_name", "", account)
    business_brief = get_setting("business_brief", "", account)
    whitelist = get_setting("whitelist", "", account)
    return render_template("settings.html", owner_name=owner_name, business_brief=business_brief, whitelist=whitelist, saved=saved)

@app.route("/regenerate", methods=["POST"])
def regenerate():
    if not session.get("credentials"):
        return redirect(url_for("connect"))

    from ai import draft_reply
    from db import save_draft, get_draft

    gmail_id = request.form.get("gmail_id")
    business_brief = get_setting("business_brief", "", current_account())

    emails = session.get("drafted_emails", [])
    email = next((e for e in emails if e["gmail_id"] == gmail_id), None)

    if email:
        new_reply = draft_reply(email["body"], email["sender"], email["subject"], business_brief)
        save_draft(gmail_id, email["sender"], email["subject"], email["body"], new_reply)
        emails = [e if e["gmail_id"] != gmail_id else {**e, "draft_reply": new_reply} for e in emails]
        session["drafted_emails"] = emails

    return render_template("dashboard.html", connected=True, emails=emails, owner_name=get_setting("owner_name", "", current_account()))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)