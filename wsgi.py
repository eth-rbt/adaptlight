"""WSGI entry point for production deployment."""
from apps.web.main import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
