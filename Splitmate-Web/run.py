import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    host = os.environ.get('FLASK_RUN_HOST') or '0.0.0.0'
    port = int(os.environ.get('FLASK_RUN_PORT') or 5000)
    # Debug mode exposes the Werkzeug console to everyone who can reach the server, so it is opt-in.
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    use_reloader = os.environ.get('FLASK_USE_RELOADER', 'false').lower() in ('1', 'true', 'yes')
    app.run(debug=debug, host=host, port=port, use_reloader=use_reloader)
