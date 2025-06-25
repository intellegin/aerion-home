from web_ui import app

# This 'app' is the Flask app instance imported from your existing web_ui.py
# Vercel will use this 'app' object to run the web server.
# The background assistant thread and app.run() from web_ui.py will not be executed. 