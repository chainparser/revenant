import uuid
from datetime import datetime, timedelta, timezone
from flask.sessions import SessionInterface, SessionMixin
from google.cloud import datastore 


class DatastoreSession(dict, SessionMixin):
    """Custom session object stored in Google Cloud Datastore."""
    def __init__(self, sid, data=None):
        super().__init__(data or {})
        self.sid = sid


class DatastoreSessionInterface(SessionInterface):
    """Flask session interface backed by Google Cloud Datastore."""

    def __init__(self, project_id, kind="user_session"):
        self.client = datastore.Client()
        self.kind = kind

    def generate_sid(self):
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def get_session_lifetime(self, app):
        """Get configured session lifetime (default 31 days)."""
        return app.permanent_session_lifetime or timedelta(days=31)

    def open_session(self, app, request):
        """Load session from datastore or create a new one."""
        sid = request.cookies.get(app.config.get("SESSION_COOKIE_NAME", "session"))
        if not sid:
            sid = self.generate_sid()
            return DatastoreSession(sid=sid)

        key = self.client.key(self.kind, sid)
        entity = self.client.get(key)

        if entity and entity["expires"] > datetime.now(timezone.utc):
            return DatastoreSession(sid=sid, data=dict(entity["data"]))

        # Expired or missing → create a new session
        return DatastoreSession(sid=self.generate_sid())

    def save_session(self, app, session, response):
        """Persist session to datastore and set cookie."""
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        httponly = self.get_cookie_httponly(app)
        secure = self.get_cookie_secure(app)
        samesite = self.get_cookie_samesite(app)

        if not session:
            # Delete session if empty
            response.delete_cookie(
                app.config.get("SESSION_COOKIE_NAME", "session"),
                domain=domain,
                path=path
            )
            return

        expires = datetime.now(timezone.utc) + self.get_session_lifetime(app)
        key = self.client.key(self.kind, session.sid)
        entity = datastore.Entity(key=key)
        entity.update({
            "data": dict(session),
            "expires": expires
        })
        self.client.put(entity)

        response.set_cookie(
            app.config.get("SESSION_COOKIE_NAME", "session"),
            session.sid,
            expires=expires,
            httponly=httponly,
            secure=secure,
            samesite=samesite,
            domain=domain,
            path=path
        )

    def cleanup_expired_sessions(self):
        """Remove expired sessions from datastore."""
        query = self.client.query(kind=self.kind)
        query.add_filter("expires", "<", datetime.now(timezone.utc))

        expired_sessions = list(query.fetch())
        if expired_sessions:
            keys = [s.key for s in expired_sessions]
            self.client.delete_multi(keys)
