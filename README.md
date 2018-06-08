# notificat.py

Prints mastodon webpushes to console

**To install:**
<pre>
git clone
cd notificat
pip install -r requirements.txt
</pre>

**Usage:**
<pre>
usage: notificat.py [-h] [-f] [-j] [-s] [-w WSS_URL] [-a AUTOPUSH_CRED_FILE]
                    [-p PORT] [-d HOSTNAME] [-c CERTBOT_EXECUTABLE]
                    [-l LETSENCRYPT_PATH]
                    instance cred_file

Prints Mastodon WebPush notifications to the terminal, either via Mozilla
Autopush (default, recommended) or by directly providing its own WebPush
endpoint (complex and very impractical.)

positional arguments:
  instance              Base URL for the instance you want to get
                        notifications from.
  cred_file             Login credentials file name. Will be created if it
                        does not exist. This file is not encrypted and will
                        allow people to access your mastodon account. Keep it
                        safe.

optional arguments:
  -h, --help            show this help message and exit
  -f, --fancy           Use colours and unicode glyphs in output.
  -j, --json            Output notifications as JSON.
  -s, --all-scopes      When logging in, create an access token that is
                        allowed full access instead of a push notification
                        only token.
  -w WSS_URL, --wss-url WSS_URL
                        (autopush mode) Websocket URL for autopush. Default:
                        ''wss://push.services.mozilla.com/'
  -a AUTOPUSH_CRED_FILE, --autopush-cred-file AUTOPUSH_CRED_FILE
                        (autopush mode) Autopush credential cache file name.
                        Default: 'autopush_sub.pkl'
  -p PORT, --port PORT  (direct mode) Port to listen on. Default: 80
  -d HOSTNAME, --direct HOSTNAME
                        Use direct WebPush mode instead of Mozilla Autopush,
                        with specified host name.
  -c CERTBOT_EXECUTABLE, --certbot-executable CERTBOT_EXECUTABLE
                        (direct mode) Certbot command. Default: 'certbot-auto'
  -l LETSENCRYPT_PATH, --letsencrypt-path LETSENCRYPT_PATH
                        (direct mode) Certbot certificate path. Default:
                        '/etc/letsencrypt/live/'

For normal client usage, it is strongly recommended that you use Mozilla
Autopush. The direct mode requires your machine to have a globally resolvable
hostname and to be reachable via at least port 80. You also need to have
certbot-auto installed and configured correctly. For autopush operation,
nothing is required - it should just work.
</pre>

**Screenshot:**

![notificat screenshot](screenshot.png?raw=true "Optional Title")
