from flask import Flask, render_template, request, redirect, url_for
from db import init_db

app = Flask(__name__)
app.secret_key = "dev-secret-key"

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
