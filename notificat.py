import os
import sys
import pickle
import subprocess
import json

import ssl
import http.server

import getpass

from mastodon import Mastodon
import styletools

###
# Settings
###
INSTANCE = "https://icosahedron.website/" # Instance we want to log into
HOST = "halcy.de" # Host name or IP of the server. Please no protocol.
PORT = 666 # Note that you still need to have port 80 open anyways for the cert request
CERTBOT_COMMAND = "/home/halcyon/ssl/certbot-auto"
CERTBOT_CERTPATH = "/etc/letsencrypt/live/"
JSON_MODE = False

###
# Real script that does stuff
###

# Get a letsencrypt certificate if we have to - requires certbot
cert_file = os.path.join(CERTBOT_CERTPATH, HOST, "fullchain.pem")
key_file = os.path.join(CERTBOT_CERTPATH, HOST, "privkey.pem")

if not os.path.exists(cert_file):
    if not os.path.exists('le_webroot'):
        os.mkdir('le_webroot')
        
    le_server = subprocess.Popen([
        'python3', 
        '-m', 'http.server', '80'
    ], cwd='le_webroot')

    subprocess.call([
        CERTBOT_COMMAND, 'certonly',
        '--agree-tos',
        '--webroot',
        '--webroot-path', 'le_webroot',
        '--domain', HOST,
        
    ])
    le_server.terminate()

# Log into Mastodon
if not os.path.exists("access_token.secret"):
    client_cred, client_secret = Mastodon.create_app('notificat', api_base_url = INSTANCE)
    api = Mastodon(client_cred, client_secret, api_base_url = INSTANCE)
    
    username = input("E-Mail: ")
    password = getpass.getpass("Password: ")
    api.log_in(username, password, to_file = "access_token.secret")
else:
    api = Mastodon(access_token = "access_token.secret", api_base_url = INSTANCE)

# Generate or load keys
if not os.path.exists("notificat_keys.secret"):
    priv_keys, pub_keys = api.push_subscription_generate_keys()

    with open('notificat_keys.secret', 'wb') as outfile:
        pickle.dump([priv_keys, pub_keys], outfile)
else:
    with open('notificat_keys.secret', 'rb') as infile:
        priv_keys, pub_keys = pickle.load(infile)

api.account_verify_credentials()
if not JSON_MODE:
    print("Logged in. Setting up stream...")

subscription = api.push_subscription_set(
    HOST + ':' + str(PORT), pub_keys, 
    follow_events = True, 
    favourite_events = True, 
    reblog_events = True,
    mention_events = True
)

if not JSON_MODE:
    print("Subscription set, waiting for pushes!\n\n")

# Define our request handler
class WebnotifyRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        enc_header = self.headers["Encryption"]
        key_header = self.headers["Crypto-Key"]
        
        enc_len = 0
        if "Content-Length" in self.headers:
            enc_len = int(self.headers["Content-Length"])
        enc_data = self.rfile.read(enc_len)
        
        dec_data = api.push_subscription_decrypt_push(enc_data, priv_keys, enc_header, key_header)
        
        if not JSON_MODE:
            avatar = styletools.get_avatar(dec_data.icon)
            print(
                "\033[1m" + styletools.ansi_rgb(1.0, 0.0, 0.5) + styletools.glyphs[dec_data.notification_type] + 
                styletools.ansi_reset() + " \033[1m" + dec_data.title
            )
            print(avatar + styletools.ansi_reset() + " \033[22m" + dec_data.body + "\n")
        else:
            print(json.dumps(dec_data))
            
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
    def log_message(self, format, *args):
        return

# Start HTTPS server
server_address = ('', PORT)
httpd = http.server.HTTPServer(
    server_address, 
    WebnotifyRequestHandler
)
httpd.socket = ssl.wrap_socket(
    httpd.socket,
    server_side = True,
    certfile = cert_file,
    keyfile = key_file,
    ssl_version = ssl.PROTOCOL_TLSv1
)
httpd.serve_forever()
