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
import mozpush
import time

###
# Settings
###
INSTANCE = "https://icosahedron.website/" # Instance we want to log into
MOZPUSH_MODE = True # Use mozillas autpush relay

# For not-mozpush mode
HOST = "halcy.de" # Host name or IP of the server. Please no protocol.
PORT = 666 # Note that you still need to have port 80 open anyways for the cert request
CERTBOT_COMMAND = "/home/halcyon/ssl/certbot-auto"
CERTBOT_CERTPATH = "/etc/letsencrypt/live/"
JSON_MODE = False

###
# Real script that does stuff
###

if not MOZPUSH_MODE:
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
    push_url = HOST + ':' + str(PORT)
else:
    client = mozpush.MozAutopushClient( 'wss://push.services.mozilla.com/')
    client.connect()
    
    if os.path.exists('mozpush_sub.pkl'):
        with open('mozpush_sub.pkl', 'rb') as infile:
            user_agent_id, channel_id = pickle.load(infile)
        
        hello_resp = client.hello(user_agent_id)
        register_resp = client.register(channel_id)
    else:
        hello_resp = client.hello()
        register_resp = client.register()
    
    user_agent_id = hello_resp['uaid']
    channel_id = register_resp['channelID']
    with open('mozpush_sub.pkl', 'wb') as outfile:
        pickle.dump([user_agent_id, channel_id], outfile)
    
    push_url = register_resp['pushEndpoint']
    ping_time = hello_resp['ping']
    
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
    push_url, pub_keys, 
    follow_events = True, 
    favourite_events = True, 
    reblog_events = True,
    mention_events = True
)

if not JSON_MODE:
    print("Subscription set, waiting for pushes!\n\n")

def print_notif(dec_data):
    if not JSON_MODE:
        avatar = styletools.get_avatar(dec_data.icon)
        print(
            "\033[1m" + styletools.ansi_rgb(1.0, 0.0, 0.5) + styletools.glyphs[dec_data.notification_type] + 
            styletools.ansi_reset() + " \033[1m" + dec_data.title
        )
        print(avatar + styletools.ansi_reset() + " \033[22m" + dec_data.body + "\n")
    else:
        print(json.dumps(dec_data))

if not MOZPUSH_MODE:
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
            print_notif(dec_data)
            
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
else:
    connected = True
    while True:
        try:
            notif = client.get_notification(timeout=ping_time * 0.95)
            if notif != None:
                dec_data = api.push_subscription_decrypt_push(
                    api._Mastodon__decode_webpush_b64(notif["data"]),
                    priv_keys,
                    notif['headers']['encryption'],
                    notif['headers']['crypto_key']
                )
                print_notif(dec_data)
            else:
                connected = client.ping()
        except Exception:
            connected = False
        
        while connected == False:
            try:
                client.connect()
                hello_resp = client.hello(user_agent_id)
                register_resp = client.register(channel_id)
            
                user_agent_id = hello_resp['uaid']
                channel_id = register_resp['channelID']
                with open('mozpush_sub.pkl', 'wb') as outfile:
                    pickle.dump([user_agent_id, channel_id], outfile)
                
                push_url = register_resp['pushEndpoint']
                ping_time = hello_resp['ping']
                
                subscription = api.push_subscription_set(
                    push_url, pub_keys, 
                    follow_events = True, 
                    favourite_events = True, 
                    reblog_events = True,
                    mention_events = True
                )
                connected = True
            except Exception:
                if not JSON_MODE:
                    print("Reconnecting to mozilla autopush...\n")
                time.sleep(5)
                    