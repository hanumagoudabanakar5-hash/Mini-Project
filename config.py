import os

class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "mini-project-development-secret"
    )

    SQLALCHEMY_DATABASE_URI = "sqlite:///mini_project.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
