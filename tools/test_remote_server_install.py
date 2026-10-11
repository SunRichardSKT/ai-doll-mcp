"""Run the actual Bash installer with isolated Docker/DNS/HTTPS substitutes.

These verify installer decisions and ownership, not a real cloud certificate.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import socket
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
BASH=Path('C:/Program Files/Git/bin/bash.exe') if os.name=='nt' else Path(shutil.which('bash') or '/missing')
TOKEN='a'*64
DOMAIN='doll.test-domain.net'


@unittest.skipUnless(BASH.is_file(), 'Bash is required')
class RemoteInstallTests(unittest.TestCase):
    def posix(self,path):
        if os.name!='nt':return str(path)
        return subprocess.check_output([str(BASH),'-c','cygpath -u "$1"','convert',str(path)],text=True).strip()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='AI Doll remote ')
        self.root=Path(self.temp.name);self.bin=self.root/'fake-bin';self.bin.mkdir()
        self.target=self.root/'install';self.command_dir=self.root/'commands'
        self.script=self.root/'Install_Server.sh';shutil.copyfile(ROOT/'Install_Server.sh',self.script)
        self.log=self.root/'docker.txt'
        self.env=dict(os.environ,PATH=self.posix(self.bin)+':/usr/bin:/bin',MSYS2_ARG_CONV_EXCL='*',
            FIXTURE_PATH=self.posix(self.bin)+':/usr/bin:/bin',
            FIXTURE_PACKAGE=self.posix(ROOT/'delivery/AI_Doll_Server_v2.16.2.tar.gz'),
            FIXTURE_LOG=self.posix(self.log),FIXTURE_TOKEN=TOKEN,FIXTURE_DOMAIN=DOMAIN,
            FIXTURE_ID=hashlib.sha256(('installation:'+TOKEN).encode()).hexdigest())
        self.stub('uname','printf "Linux\\n"')
        self.stub('id','printf "0\\n"')
        self.stub('flock','exit 0')
        self.stub('getent','[[ "${FIXTURE_DNS_FAIL:-}" != 1 ]] && printf "203.0.113.1\\n"')
        self.stub('docker',r'''
printf '%s\n' "$*" >> "$FIXTURE_LOG"
if [[ "$1" == ps ]]; then
  if [[ "${FIXTURE_PROJECT_EXISTS:-}" == 1 ]]; then
    if [[ "$*" == *--format* ]]; then printf 'doll\nhttps\n'; else printf 'fixture-container\n'; fi
  fi
  exit 0
fi
if [[ "$*" == *'exec -T doll'* ]]; then printf '%s\n' "$FIXTURE_TOKEN"; fi
exit 0
''')
        self.stub('curl',r'''
output=''; url=''
while (( $# )); do
  case "$1" in -o) output=$2;shift 2;; --config) shift 2;; *) [[ "$1" == https://* ]] && url=$1;shift;; esac
done
if [[ -n "$output" ]]; then
  if [[ "$url" == *.sha256 ]]; then
    if [[ "${FIXTURE_BAD_HASH:-}" == 1 ]]; then printf '%064d  fixture.tar.gz\n' 0 > "$output"
    else sha256sum "$FIXTURE_PACKAGE" > "$output";fi
  else cp "$FIXTURE_PACKAGE" "$output";fi
else
  cat >/dev/null
  [[ "${FIXTURE_HTTPS_FAIL:-}" != 1 ]] || exit 60
  printf '{"installation_id": "%s", "server_url": "https://%s"}\n' "$FIXTURE_ID" "$FIXTURE_DOMAIN"
fi
''')

    def stub(self,name,body):
        path=self.bin/name;path.write_text('#!/usr/bin/env bash\n'+body+'\n',encoding='utf-8',newline='\n')
        path.chmod(0o755)

    def tearDown(self):self.temp.cleanup()

    def run_install(self,*args,domain=True,**environment):
        # Git's Windows launcher prepends its own tools to PATH. Set the isolated
        # PATH after launch so all system actions use the declared substitutes.
        command=[str(BASH),'-c','export PATH="$FIXTURE_PATH"; source "$1"; shift; main "$@"',
                 'installer-test',self.posix(self.script),'--install-dir',self.posix(self.target),
                 '--bin-dir',self.posix(self.command_dir),'--wait-sec','1']
        if domain:command+=['--domain',DOMAIN]
        return subprocess.run(command+list(args),env=dict(self.env,**environment),capture_output=True,
                              text=True,encoding='utf-8',timeout=30)

    def test_download_install_repeat_and_stop_preserve_state(self):
        first=self.run_install();self.assertEqual(first.returncode,0,first.stderr)
        self.assertIn('部署与 HTTPS 验证通过',first.stdout)
        saved=(self.target/'connection-private.txt').read_bytes()
        self.assertTrue((self.target/'tools/direct_server.py').is_file())
        self.assertEqual((self.target/'deploy/direct-server/.env').read_text().strip(),'DOLL_DOMAIN='+DOMAIN)
        sentinel=self.target/'history-sentinel';sentinel.write_text('preserve')
        repeat=self.run_install(domain=False);self.assertEqual(repeat.returncode,0,repeat.stderr)
        self.assertEqual((self.target/'connection-private.txt').read_bytes(),saved)
        stop=self.run_install('--action','stop',domain=False);self.assertEqual(stop.returncode,0,stop.stderr)
        self.assertEqual(sentinel.read_text(),'preserve')
        self.assertNotIn('down -v',self.log.read_text())
        self.assertTrue((self.command_dir/'ai-doll-server').is_file())

    def test_invalid_domain_and_unknown_directory_have_no_docker_actions(self):
        for domain in ('https://doll.test-domain.net','doll.test-domain.net:443','a..net','example.com','$(touch x).net'):
            result=self.run_install('--domain',domain)
            self.assertNotEqual(result.returncode,0)
        self.target.mkdir();sentinel=self.target/'other.txt';sentinel.write_text('other project')
        result=self.run_install();self.assertNotEqual(result.returncode,0)
        self.assertEqual(sentinel.read_text(),'other project');self.assertFalse(self.log.exists())

    def test_dns_failure_does_not_start_services(self):
        result=self.run_install(FIXTURE_DNS_FAIL='1')
        self.assertNotEqual(result.returncode,0);self.assertIn('尚未解析',result.stderr)
        self.assertFalse(self.log.exists())

    def test_https_failure_never_reports_success(self):
        result=self.run_install(FIXTURE_HTTPS_FAIL='1')
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertIn('HTTPS 尚未通过',result.stderr);self.assertNotIn('验证通过',result.stdout)
        self.assertTrue((self.target/'deployment-private.conf').exists())
        self.assertFalse((self.target/'connection-private.txt').exists())

    def test_bad_checksum_can_retry_without_partial_extraction(self):
        bad=self.run_install(FIXTURE_BAD_HASH='1');self.assertNotEqual(bad.returncode,0)
        self.assertFalse((self.target/'tools').exists())
        retry=self.run_install();self.assertEqual(retry.returncode,0,retry.stderr)

    def test_existing_default_project_requires_explicit_adoption(self):
        result=self.run_install(FIXTURE_PROJECT_EXISTS='1')
        self.assertNotEqual(result.returncode,0);self.assertIn('未接管',result.stderr)
        explicit=self.run_install('--project','existing-doll',FIXTURE_PROJECT_EXISTS='1')
        self.assertEqual(explicit.returncode,0,explicit.stderr)

    def test_preview_is_read_only(self):
        result=self.run_install('--dry-run')
        self.assertEqual(result.returncode,0);self.assertFalse(self.target.exists())
        self.assertFalse(self.log.exists())

    def test_minimal_payload_serves_authenticated_management(self):
        payload=self.root/'payload';payload.mkdir()
        with tarfile.open(ROOT/'delivery/AI_Doll_Server_v2.16.2.tar.gz','r:gz') as archive:
            archive.extractall(payload,filter='data')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        code='import sys;sys.path.insert(0,sys.argv.pop(1));import direct_server;direct_server.main()'
        child=subprocess.Popen([sys.executable,'-X','utf8','-c',code,str(payload/'tools'),
            '--listen','127.0.0.1','--port',str(port),'--data-dir',str(payload/'data'),
            '--public-url','https://'+DOMAIN],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            deadline=time.monotonic()+8
            while True:
                try:
                    with opener.open(f'http://127.0.0.1:{port}/healthz',timeout=1) as response:
                        self.assertTrue(json.load(response)['ready'])
                    break
                except OSError:
                    if time.monotonic()>=deadline:raise
                    time.sleep(.1)
            private=json.loads((payload/'data/server-private.json').read_text())
            request=urllib.request.Request(f'http://127.0.0.1:{port}/api/server',
                headers={'Authorization':'Bearer '+private['admin_token']})
            with opener.open(request,timeout=2) as response:status=json.load(response)
            self.assertFalse(status['local_setup'])
            self.assertEqual(status['server_url'],'https://'+DOMAIN)
        finally:
            if child.poll() is None:child.terminate()
            child.wait(timeout=5)


if __name__=='__main__':unittest.main()
