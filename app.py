from flask import Flask, redirect, url_for, session, render_template
from authlib.integrations.flask_client import OAuth

from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecret"  # replace with secure key in production
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

@app.route("/")
def index():
    user = session.get("user")
    if user:
        return render_template("dashboard.html", user=user)
    return render_template("index.html")

@app.route("/login")
def login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/callback")
def authorize():
    token = google.authorize_access_token()
    resp = google.get("userinfo")
    user_info = resp.json()
    session["user"] = user_info
    return redirect("/")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
