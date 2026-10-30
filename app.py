from flask import Flask
from flask_login import LoginManager

from config import Config
from models import db, Admin
from routes.auth import auth
from routes.pages import pages

app = Flask(__name__)

app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))


app.register_blueprint(auth)
app.register_blueprint(pages)


@app.route("/")
def home():
    from flask import redirect, url_for
    return redirect(url_for("auth.login"))


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
