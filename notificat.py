#!/usr/bin/python3

import os
import sys
import pickle
import argparse
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
# Argument parsing
###
parser = argparse.ArgumentParser(
    description = "Prints Mastodon WebPush notifications to the terminal, either via Mozilla Autopush (default, recommended) or by directly providing its own WebPush endpoint (complex and very impractical.)",
    epilog = "For normal client usage, it is strongly recommended that you use Mozilla Autopush. The direct mode requires your machine to have a globally resolvable hostname and to be reachable via at least port 80. You also need to have certbot-auto installed and configured correctly. For autopush operation, nothing is required - it should just work."
)

parser.add_argument("-f", "--fancy", help="Use colours and unicode glyphs in output.", action="store_true")
parser.add_argument("-j", "--json", help="Output notifications as JSON.", action="store_true")
parser.add_argument("-s", "--all-scopes", help="When logging in, create an access token that is allowed full access instead of a push notification only token.", action="store_true")
parser.add_argument("-w", "--wss-url", help="(autopush mode) Websocket URL for autopush. Default: ''wss://push.services.mozilla.com/'", action="store", type=str, default='wss://push.services.mozilla.com/')
parser.add_argument("-a", "--autopush-cred-file", help="(autopush mode) Autopush credential cache file name. Default: 'autopush_sub.pkl'", action="store", type=str, default='autopush_sub.pkl')
parser.add_argument("-p", "--port", help="(direct mode) Port to listen on. Default: 80", action="store", type=int, default=80)
parser.add_argument("-d", "--direct", metavar="HOSTNAME", help="Use direct WebPush mode instead of Mozilla Autopush, with specified host name.", action="store", type=str, default=None)
parser.add_argument("-c", "--certbot-executable", help="(direct mode) Certbot command. Default: 'certbot-auto'", action="store", type=str, default='certbot-auto')
parser.add_argument("-l", "--letsencrypt-path", help="(direct mode) Certbot certificate path. Default: '/etc/letsencrypt/live/'", action="store", type=str, default='/etc/letsencrypt/live/')
parser.add_argument("instance", help="Base URL for the instance you want to get notifications from.")
parser.add_argument("cred_file", help="Login credentials file name. Will be created if it does not exist. This file is not encrypted and will allow people to access your mastodon account. Keep it safe.")
args = parser.parse_args()

###
# Settings
###
# For everything
INSTANCE = args.instance # Instance we want to log into
CRED_FILE = args.cred_file # Credential file
SCOPES = ["push"]
if args.all_scopes:
    SCOPES = ["read", "write", "follow", "push"]
MOZPUSH_MODE = True # Use mozillas autpush relay
if args.direct != None:
    MOZPUSH_MODE = False

# For mozpush mode
AUTOPUSH_URL = args.wss_url
AUTOPUSH_CREDFILE = args.autopush_cred_file

# For not-mozpush mode
HOST = args.direct # Host name or IP of the server. Please no protocol.
PORT = args.port # Note that you still need to have port 80 open anyways for the cert request
CERTBOT_COMMAND = args.certbot_executable
CERTBOT_CERTPATH = args.letsencrypt_path
JSON_MODE = args.json
FANCY_MODE = args.fancy
if JSON_MODE == True and FANCY_MODE == True:
    print(sys.argv[0] + ": error: -f/--fancy and -j/--json are mutually exclusive.")
    sys.exit(-1)
    
###
# Real script that does stuff
###
if not MOZPUSH_MODE: # Direct mode
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
else: # Autopush mode
    # Set up autopush
    client = mozpush.MozAutopushClient(AUTOPUSH_URL)
    client.connect()
    
    if os.path.exists(AUTOPUSH_CREDFILE):
        with open(AUTOPUSH_CREDFILE, 'rb') as infile:
            user_agent_id, channel_id = pickle.load(infile)
        
        hello_resp = client.hello(user_agent_id)
        register_resp = client.register(channel_id)
    else:
        hello_resp = client.hello()
        register_resp = client.register()
    
    user_agent_id = hello_resp['uaid']
    channel_id = register_resp['channelID']
    with open(AUTOPUSH_CREDFILE, 'wb') as outfile:
        pickle.dump([user_agent_id, channel_id], outfile)
    
    push_url = register_resp['pushEndpoint']
    ping_time = hello_resp['ping']
    
# Log into Mastodon
if not os.path.exists(CRED_FILE):
    client_cred, client_secret = Mastodon.create_app('notificat', api_base_url = INSTANCE, scopes = SCOPES)
    api = Mastodon(client_cred, client_secret, api_base_url = INSTANCE)
    
    print("Logging in to " + str(INSTANCE))
    username = input("E-Mail: ")
    password = getpass.getpass("Password: ")
    access_token = api.log_in(username, password, scopes = SCOPES)
    
    # Generate keys
    priv_keys, pub_keys = api.push_subscription_generate_keys()

    with open(CRED_FILE, 'wb') as outfile:
        pickle.dump([access_token, priv_keys, pub_keys], outfile)
else:
    with open(CRED_FILE, 'rb') as infile:
        access_token, priv_keys, pub_keys = pickle.load(infile)
    api = Mastodon(access_token = access_token, api_base_url = INSTANCE)

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
        if FANCY_MODE:
            avatar = styletools.get_avatar(dec_data.icon)
            print(
                "\033[1m" + styletools.ansi_rgb(1.0, 0.0, 0.5) + styletools.glyphs[dec_data.notification_type] + 
                styletools.ansi_reset() + " \033[1m" + dec_data.title
            )
            print(avatar + styletools.ansi_reset() + " \033[22m" + dec_data.body + "\n")
        else:
            print(dec_data.notification_type + ": " + dec_data.title)
            print(dec_data.body + "\n")
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
                with open(AUTOPUSH_CREDFILE, 'wb') as outfile:
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
                    
