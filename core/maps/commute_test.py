import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from core.maps import commute

class CommuteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'commute.json'
    def test_no_implicit_location_or_work_guess(self):
        self.assertIsNone(commute.context('tell me a joke',path=self.path))
        self.assertIn('no owner-saved',commute.context('how long to drive to work?',path=self.path))
    def test_saved_endpoints_use_real_router(self):
        commute.save([{'lat':47,'lon':-122},{'lat':48,'lon':-123}],path=self.path)
        calls=[]
        text=commute.context('how long to drive to work?',path=self.path,router=lambda s:calls.append(s) or {'duration':1200,'distance':16093.44,'engine':'local'})
        self.assertEqual(calls[0][0]['lat'],47)
        self.assertIn('"minutes": 20',text);self.assertIn('not live GPS',text)
    def test_failed_route_never_invents_eta(self):
        commute.save([{'lat':47,'lon':-122},{'lat':48,'lon':-123}],path=self.path)
        self.assertIn('unavailable',commute.context('drive to work',path=self.path,router=lambda _:1/0))
    def test_memory_denial_blocks_mail_and_route_reads(self):
        from core.brain.brain_service import BrainService
        with patch('core.email_watch.service.email_context') as mail,patch('core.maps.commute.context') as route:
            BrainService(memory_authorizer=lambda _:False).load_behavior_context('Any important mail before I drive to work?')
            mail.assert_not_called();route.assert_not_called()
