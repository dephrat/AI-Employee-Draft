import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from gmail import get_oauth_flow, credentials_to_dict
from concurrent.futures import ThreadPoolExecutor
from google.auth.exceptions import RefreshError
from db import init_db, get_db, get_setting, save_setting, delete_draft, get_draft
import time
from crawler import crawl_website
from db import get_website_content, get_website_crawled_at, save_website_content

load_dotenv()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

def current_account():
    return session.get("account_email")

def get_emails_from_db(gmail_ids):
    return [get_draft(gid) for gid in gmail_ids if get_draft(gid)]

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
    from db import save_draft

    service = get_gmail_service(session["credentials"])
    whitelist = [e.strip() for e in get_setting("whitelist", "", current_account()).split(",") if e.strip()]
    business_brief = get_setting("business_brief", "", current_account())

    website_url = get_setting("website_url", "", current_account())
    crawled_at = get_website_crawled_at(current_account())
    if website_url and (not crawled_at or time.time() - crawled_at > 86400):
        content = crawl_website(website_url)
        save_website_content(current_account(), content)
    else:
        content = get_website_content(current_account())

    if content:
        business_brief = business_brief + "\n\nWebsite content:\n" + content

    emails = get_new_emails(service, whitelist)

    def process_email(email):
        existing = get_draft(email["gmail_id"])
        if existing:
            return existing["gmail_id"]
        reply = draft_reply(email["body"], email["sender"], email["subject"], business_brief)
        save_draft(email["gmail_id"], email["sender"], email["subject"], email["body"], reply)
        return email["gmail_id"]

    with ThreadPoolExecutor() as executor:
        gmail_ids = list(executor.map(process_email, emails))

    session["drafted_email_ids"] = gmail_ids
    results = get_emails_from_db(gmail_ids)
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

    ids = session.get("drafted_email_ids", [])
    ids = [i for i in ids if i != gmail_id]
    session["drafted_email_ids"] = ids
    emails = get_emails_from_db(ids)

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

    ids = session.get("drafted_email_ids", [])
    ids = [i for i in ids if i != gmail_id]
    session["drafted_email_ids"] = ids
    emails = get_emails_from_db(ids)

    return render_template("dashboard.html", connected=True, emails=emails, owner_name=get_setting("owner_name", "", current_account()))

@app.route("/settings", methods=["GET", "POST"])
def settings():
    saved = False
    account = current_account()
    if request.method == "POST":
        save_setting("owner_name", request.form.get("owner_name"), account)
        save_setting("business_brief", request.form.get("business_brief"), account)
        save_setting("whitelist", request.form.get("whitelist"), account)
        save_setting("website_url", request.form.get("website_url"), account)
        saved = True

    owner_name = get_setting("owner_name", "", account)
    business_brief = get_setting("business_brief", "", account)
    whitelist = get_setting("whitelist", "", account)
    website_url = get_setting("website_url", "", account)
    return render_template("settings.html", owner_name=owner_name, business_brief=business_brief, whitelist=whitelist, website_url=website_url, saved=saved)

@app.route("/regenerate", methods=["POST"])
def regenerate():
    if not session.get("credentials"):
        return redirect(url_for("connect"))

    from ai import draft_reply
    from db import save_draft

    gmail_id = request.form.get("gmail_id")
    business_brief = get_setting("business_brief", "", current_account())

    existing = get_draft(gmail_id)
    if existing:
        new_reply = draft_reply(existing["body"], existing["sender"], existing["subject"], business_brief)
        save_draft(gmail_id, existing["sender"], existing["subject"], existing["body"], new_reply)

    ids = session.get("drafted_email_ids", [])
    emails = get_emails_from_db(ids)

    return render_template("dashboard.html", connected=True, emails=emails, owner_name=get_setting("owner_name", "", current_account()))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)