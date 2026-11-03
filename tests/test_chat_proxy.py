import unittest
from news_atlas import chat_proxy
class Fake:
    client_address=('127.0.0.1',12345)
    command='POST'
    path='/api/chat/session'
    def __init__(self,headers):self.headers=headers;self.result=None
    def json_response(self,status,body):self.result=(status,body)
class ChatBoundaryTests(unittest.TestCase):
    def test_other_origin_cannot_use_local_login(self):
        for headers in [{'Host':'127.0.0.1:8765','Origin':'https://evil.example'}, {'Host':'127.0.0.1:8765'}, {'Host':'example.com','Origin':'http://example.com'}, {'Host':'localhost:8765','Origin':'http://localhost:8765','Sec-Fetch-Site':'cross-site'}]:
            h=Fake(headers);chat_proxy.handle(h);self.assertEqual(h.result[0],403)
    def test_remote_peer_cannot_spoof_loopback_host(self):
        h=Fake({'Host':'localhost:8765','Origin':'http://localhost:8765'});h.client_address=('203.0.113.12',1);chat_proxy.handle(h);self.assertEqual(h.result[0],403)
    def test_mcp_is_not_exposed_through_browser_proxy(self):
        h=Fake({'Host':'localhost:8765','Origin':'http://localhost:8765'});h.path='/api/chat/tool';chat_proxy.handle(h);self.assertEqual(h.result[0],404)
