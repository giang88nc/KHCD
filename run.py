import os
from khcd import create_app
from waitress import serve

app = create_app()
if __name__ == '__main__':
    serve(app, host=os.getenv('APP_HOST','127.0.0.1'), port=int(os.getenv('APP_PORT','8201')), threads=8,
          trusted_proxy='127.0.0.1',
          trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto','x-forwarded-host'},
          clear_untrusted_proxy_headers=True)
