from werkzeug.middleware.proxy_fix import ProxyFix
from flask_app import app
application = app

#We set the app to use a reverse proxy configured in an apache vhost
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)


