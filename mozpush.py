import websocket
import socket
import json
import uuid

class MozAutopushClient():
    def __init__(self, url):
        self.url = url
        self.ws = None
        self.notif_queue = []
        
    def connect(self):
        url = self.url
        self.ws = websocket.create_connection(url)
        return self.ws.connected

    def recv(self, timeout = None):
        orig_timeout = self.ws.gettimeout()
        self.ws.settimeout(timeout)
        while True:
            try:
                recv_str = '{}'
                while recv_str == '{}':
                    recv_str = self.ws.recv()
            except socket.timeout:
                return None
            finally:
                self.ws.settimeout(orig_timeout)
                
            recv_json = json.loads(recv_str)
        
            if recv_json['messageType'] == 'notification':
                self.notif_queue.append(recv_json)
            else:
                return recv_json

    def hello(self, user_agent_id = None):
        hello_dict = {
            'messageType': 'hello',
            'use_webpush': True,
        }
        if user_agent_id != None:
            hello_dict["uaid"] = user_agent_id
        self.ws.send(json.dumps(hello_dict))
        hello_resp = self.recv()
        return hello_resp
    
    def register(self, channel_id = None):
        if channel_id == None:
            channel_id = str(uuid.uuid4())
        msg = json.dumps({
            'messageType': 'register',
            'channelID': channel_id
        })
        self.ws.send(msg)
        return self.recv()

    def unregister(self, channel_id):
        msg = json.dumps({
            'messageType': 'unregister', 
            'channelID': channel_id,
        })
        self.ws.send(msg)
        return self.recv()

    def get_notification(self, timeout = None):
        orig_timeout = self.ws.gettimeout()
        self.ws.settimeout(timeout)
        try:
            if len(self.notif_queue) != 0:
                notif = self.notif_queue.pop()
            else:
                notif_str = '{}'
                while notif_str == '{}':
                    notif_str = self.ws.recv()
                notif = json.loads(notif_str)
            msg = json.dumps({
                'messageType': 'ack',
                'updates': [{
                    'channelID': notif['channelID'], 
                    'version': notif['version']
                
                }]
            })
            self.ws.send(msg)
            return notif
        except socket.timeout:
            return None
        finally:
            self.ws.settimeout(orig_timeout)

    def ping(self):
        self.ws.send("{}")
        return self.ws.connected
    
    def disconnect(self):
        self.ws.close()