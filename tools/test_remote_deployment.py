"""Deployment fault paths, safe ownership and Sakura dedicated-forwarder constraints."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import deploy_mcp as deployment
import owned_processes as owned
from private_storage import write_json
from sakura_frp import configure_tunnel, validate_forward_config, SakuraError

FORWARD='[common]\nserver_addr = fixture.example\ntoken = PRIVATE-FIXTURE\n[only-tunnel]\ntype = tcp\nlocal_ip = 127.0.0.1\nlocal_port = 8771\nauto_https = auto\n'


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        write_json(self.folder/'sakura-private.json',dict(origin='https://fixture.example',tunnel_id=42,
                                                        token='PRIVATE-FIXTURE',profile='interaction'))
    def tearDown(self):self.temp.cleanup()

    def test_ownership_real_child_and_pid_reuse_never_kills_it(self):
        child,value=owned.launch([sys.executable,'-c','import time;time.sleep(30)'],self.folder)
        try:
            self.assertTrue(owned.alive(value))
            reused=dict(value,born=int(value['born'])+1)
            self.assertFalse(owned.alive(reused));self.assertFalse(owned.terminate(reused))
            self.assertIsNone(child.poll())
            self.assertTrue(owned.terminate(value))
            child.wait(timeout=6);self.assertFalse(owned.alive(value))
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=6)

    @unittest.skipUnless(os.name=='nt','Windows supervisor job ownership')
    def test_supervisor_crash_cleans_child_before_registry_write(self):
        evidence=self.folder/'child.json'
        code="import sys,json,time;from owned_processes import OwnedChildJob,launch;job=OwnedChildJob();c,v=launch([sys.executable,'-c','import time;time.sleep(30)'],'.');open(sys.argv[1],'w').write(json.dumps(v));time.sleep(30)"
        parent,value=owned.launch([sys.executable,'-c',code,str(evidence)],self.folder)
        child=None
        try:
            for _ in range(50):
                if evidence.exists():break
                if parent.poll() is not None:break
                time.sleep(.1)
            self.assertTrue(evidence.exists(),'Windows job initialization failed')
            child=json.loads(evidence.read_text());self.assertTrue(owned.alive(child))
            self.assertTrue(owned.terminate(value));parent.wait(timeout=5)
            for _ in range(50):
                if not owned.alive(child):break
                time.sleep(.1)
            self.assertFalse(owned.alive(child),'Child survived its own supervisor crash')
        finally:
            if parent.poll() is None:owned.terminate(value);parent.wait(timeout=5)
            if child and owned.alive(child):owned.terminate(child)

    def test_idempotent_start_and_foreign_port_not_adopted(self):
        write_json(self.folder/'processes.json',dict(supervisor=owned.record(__import__('os').getpid())))
        with patch('deploy_mcp.launch',side_effect=AssertionError('Started a duplicate')):
            self.assertTrue(deployment.start(self.folder)['reused'])
        write_json(self.folder/'processes.json',{})
        with patch('deploy_mcp.occupied',return_value=True),patch('deploy_mcp.launch') as launch:
            with self.assertRaisesRegex(RuntimeError,'unowned'):deployment.start(self.folder)
            launch.assert_not_called()

    def test_supervisor_retries_failure_and_stops_owned_children(self):
        me=owned.record(__import__('os').getpid())
        write_json(self.folder/'processes.json',dict(supervisor=me))
        arguments=[]
        def launch(argv,cwd):
            arguments.append(argv)
            return Mock(),dict(pid=10000+len(arguments),born=1,executable='fixture')
        checks=0
        def verify(*a,**k):
            nonlocal checks
            checks+=1
            if checks==1:raise RuntimeError('fixture disconnect')
            write_json(self.folder/'stop.json',{})
            return dict(protocol_connected=True,trusted_https=True,checked_at=time.time())
        with patch('deploy_mcp.OwnedChildJob'),patch('deploy_mcp.alive',side_effect=lambda v:bool(v)),patch('deploy_mcp.occupied',return_value=False),\
             patch('deploy_mcp.launch',side_effect=launch),patch('deploy_mcp.install_client',return_value=(self.folder/'frpc.exe','fixture')),\
             patch('deploy_mcp.configure_tunnel',return_value=self.folder/'frpc-private.ini'),patch('deploy_mcp.verify',side_effect=verify),\
             patch('deploy_mcp.terminate',return_value=True) as stop:
            deployment.supervise(self.folder)
            self.assertEqual(checks,2);self.assertEqual(len(arguments),2)
            self.assertEqual(stop.call_count,2)
        self.assertNotIn('PRIVATE-FIXTURE',json.dumps(arguments))
        self.assertFalse(deployment.status(self.folder)['remote_connected'])

    def test_client_managed_supervisor_never_requests_token_or_touches_external_client(self):
        write_json(self.folder/'sakura-private.json',dict(origin='https://fixture.example',
                   profile='interaction',tunnel_management='client'))
        self.assertNotIn('token', deployment.config(self.folder))
        write_json(self.folder/'processes.json',dict(supervisor=owned.record(os.getpid())))
        def ready(*args,**kwargs):
            write_json(self.folder/'stop.json',{})
            return dict(protocol_connected=True,trusted_https=True,checked_at=time.time())
        with patch('deploy_mcp.OwnedChildJob'), patch('deploy_mcp.alive',side_effect=lambda v:bool(v)), \
             patch('deploy_mcp.occupied',return_value=False), \
             patch('deploy_mcp.launch',return_value=(Mock(),dict(pid=10001,born=1,executable='fixture'))) as launch, \
             patch('deploy_mcp.install_client',side_effect=AssertionError('Sakura download attempted')), \
             patch('deploy_mcp.SakuraAPI',side_effect=AssertionError('Sakura account API used')), \
             patch('deploy_mcp.configure_tunnel',side_effect=AssertionError('External tunnel edited')), \
             patch('deploy_mcp.verify',side_effect=ready), patch('deploy_mcp.terminate',return_value=True) as stop:
            deployment.supervise(self.folder)
            self.assertEqual(launch.call_count,1)
            self.assertIn('remote_mcp.py',launch.call_args.args[0][1])
            self.assertEqual(stop.call_count,1)

    def test_client_managed_readiness_requires_live_gateway_and_actual_https(self):
        cfg=dict(origin='https://fixture.example',profile='interaction',tunnel_management='client')
        write_json(self.folder/'sakura-private.json',cfg)
        write_json(self.folder/'processes.json',dict(supervisor=owned.record(os.getpid()),gateway=owned.record(os.getpid())))
        write_json(self.folder/'deployment-status.json',dict(protocol_connected=False,checked_at=time.time()))
        self.assertFalse(deployment.status(self.folder)['remote_connected'])
        write_json(self.folder/'deployment-status.json',dict(protocol_connected=True,trusted_https=True,checked_at=time.time()))
        self.assertTrue(deployment.status(self.folder)['remote_connected'])
        write_json(self.folder/'deployment-status.json',dict(protocol_connected=True,trusted_https=True,checked_at=time.time()-120))
        self.assertFalse(deployment.status(self.folder)['remote_connected'])
        write_json(self.folder/'sakura-private.json',dict(cfg,token='PRIVATE-FIXTURE'))
        with self.assertRaisesRegex(ValueError,'must not contain'):deployment.config(self.folder)

    def test_failed_verification_replaces_stale_success_and_reset_keeps_history(self):
        write_json(self.folder/'remote-check.json',dict(protocol_connected=True,trusted_https=True))
        with patch('deploy_mcp.probe_url',side_effect=RuntimeError('https://PRIVATE-FIXTURE/mcp')):
            failed=deployment.verify(self.folder,calls=True)
        self.assertFalse(failed['protocol_connected'])
        self.assertNotIn('PRIVATE-FIXTURE',(self.folder/'remote-check.json').read_text())
        deployment.save_connection(self.folder,deployment.config(self.folder))
        old=json.loads((self.folder/'chatgpt-connection-private.json').read_text())['url']
        history=self.folder/'history.sqlite3';history.write_bytes(b'preserve')
        deployment.reset_address(self.folder)
        new=json.loads((self.folder/'chatgpt-connection-private.json').read_text())['url']
        self.assertNotEqual(old,new);self.assertEqual(history.read_bytes(),b'preserve')

    def test_periodic_health_preserves_actual_call_evidence(self):
        evidence=dict(protocol_connected=True,status_calls={'get_installation_status':{'call_id':'fixture-proof'}})
        write_json(self.folder/'remote-check.json',evidence)
        with patch('deploy_mcp.probe_url',side_effect=RuntimeError('fixture disconnect')):
            health=deployment.verify(self.folder,calls=False)
        self.assertFalse(health['protocol_connected'])
        self.assertEqual(json.loads((self.folder/'remote-check.json').read_text()),evidence)
        self.assertFalse(json.loads((self.folder/'remote-health-check.json').read_text())['protocol_connected'])


class SakuraConfigTests(unittest.TestCase):
    def test_only_designated_tunnel_is_edited_and_credentials_not_in_arguments(self):
        tunnel=dict(id=42,type='tcp',status=0,local_ip='localhost',local_port=8768,extra='auto_https = auto')
        api=Mock();api.request.side_effect=[[tunnel,dict(id=99)],{},FORWARD]
        with tempfile.TemporaryDirectory() as folder:
            path=configure_tunnel(api,42,'0.51.0-sakura-15',folder)
            self.assertEqual(path.read_text(),FORWARD)
        self.assertEqual(api.request.call_args_list[1].args,('/tunnel/edit',dict(id=42,local_ip='127.0.0.1',local_port=8771)))
        self.assertEqual(api.request.call_args_list[2].args[1]['query'],'42')

    def test_reject_management_forward_plugin_multiple_tunnels_and_https_backend(self):
        for raw in (FORWARD.replace('8771','8768'),FORWARD.replace('127.0.0.1','0.0.0.0'),
                    FORWARD+'plugin = static_file\n',FORWARD+'[second]\ntype = tcp\n',
                    FORWARD.replace('type = tcp','type = https')):
            with self.assertRaises(SakuraError):validate_forward_config(raw)
        for tunnel in (dict(id=42,type='https',status=0),dict(id=42,type='tcp',status=0,extra=''),dict(id=42,type='tcp',status=2)):
            api=Mock();api.request.return_value=[tunnel]
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(SakuraError):configure_tunnel(api,42,'fixture',folder)
        self.assertEqual(validate_forward_config(FORWARD),FORWARD)


if __name__=='__main__':unittest.main()
