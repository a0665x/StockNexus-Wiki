import os,unittest
from unittest.mock import patch
from news_atlas import chat_proxy
from test_chat_proxy import Fake

class TailscaleChatTests(unittest.TestCase):
 def request(self,changes=None,peer='127.0.0.1'):
  h=Fake({'Host':'host.tail.test:8765','Origin':'https://host.tail.test:8765','Tailscale-User-Login':'owner@example.test',**(changes or {})});h.path='/api/chat/tool';h.client_address=(peer,1)
  with patch.dict(os.environ,{'NEWS_ATLAS_CHAT_ORIGINS':'https://host.tail.test:8765','NEWS_ATLAS_CHAT_TAILSCALE_USERS':'owner@example.test'}):chat_proxy.handle(h)
  return h.result[0]
 def test_authorized_tailnet_identity_passes_origin_gate_but_not_tool_route(self):self.assertEqual(self.request(),404)
 def test_missing_or_other_identity_is_denied(self):
  for user in ['', 'other@example.test']:self.assertEqual(self.request({'Tailscale-User-Login':user}),403)
 def test_cross_origin_and_cross_site_are_denied(self):
  for change in [{'Origin':'https://evil.test'},{'Origin':''},{'Origin':'http://host.tail.test:8765'},{'Sec-Fetch-Site':'cross-site'},{'Host':'evil.test'}]:self.assertEqual(self.request(change),403)
 def test_remote_peer_cannot_forge_proxy_identity(self):self.assertEqual(self.request(peer='203.0.113.2'),403)
if __name__=='__main__':unittest.main()
