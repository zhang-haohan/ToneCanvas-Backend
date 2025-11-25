from werkzeug.middleware.proxy_fix import ProxyFix
from flask_app import app
application = app

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

if __name__ == '__main__':
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='fullchain.pem', keyfile='privkey.pem')
    #import logging
    #logging.basicConfig(filename='flaskerror.log',level=logging.DEBUG)
    app.run(debug=True,ssl_context=context, host= '0.0.0.0', port=5000)
