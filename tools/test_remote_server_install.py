"""Run the actual Bash installer with isolated Docker/DNS/HTTPS substitutes.

These verify installer decisions and ownership, not a real cloud certificate.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
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
        return subprocess.check_output([str(BASH),'-c','cygpath -u "$1"','convert',str(path)],
                                       text=True,encoding='utf-8').strip()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='AI Doll remote ')
        self.root=Path(self.temp.name);self.bin=self.root/'fake-bin';self.bin.mkdir()
        self.target=self.root/'install';self.command_dir=self.root/'commands'
        self.script=self.root/'Install_Server.sh';shutil.copyfile(ROOT/'Install_Server.sh',self.script)
        self.log=self.root/'docker.txt'
        self.env=dict(os.environ,PATH=self.posix(self.bin)+':/usr/bin:/bin',MSYS2_ARG_CONV_EXCL='*',
            FIXTURE_PATH=self.posix(self.bin)+':/usr/bin:/bin',
            FIXTURE_PACKAGE=self.posix(ROOT/'delivery/AI_Doll_Server_v2.25.1.tar.gz'),
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
if [[ " $* " == *' up '* && " $* " == *' --build '* ]]; then
  # Check the actual installed Dockerfile's COPY inputs before pretending that
  # the build succeeded. This fixture supports this project's plain COPY form.
  args=("$@"); project_dir=''
  for ((i=0;i<${#args[@]};i++)); do
    [[ "${args[i]}" != --project-directory ]] || project_dir=${args[i+1]}
  done
  while read -r instruction rest; do
    [[ "$instruction" == COPY ]] || continue
    read -ra fields <<< "$rest"
    for ((i=0;i<${#fields[@]}-1;i++)); do
      [[ "${fields[i]}" == --* ]] && continue
      [[ -e "$project_dir/../../${fields[i]}" ]] || { printf 'Missing Docker COPY source: %s\n' "${fields[i]}" >&2; exit 31; }
    done
  done < "$project_dir/Dockerfile"
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

    def run_install(self,*args,domain=True,stdin='',**environment):
        # Git's Windows launcher prepends its own tools to PATH. Set the isolated
        # PATH after launch so all system actions use the declared substitutes.
        command=[str(BASH),'-c','export PATH="$FIXTURE_PATH"; source "$1"; shift; main "$@"',
                 'installer-test',self.posix(self.script),'--install-dir',self.posix(self.target),
                 '--bin-dir',self.posix(self.command_dir),'--wait-sec','1']
        if domain:command+=['--domain',DOMAIN]
        return subprocess.run(command+list(args),env=dict(self.env,**environment),capture_output=True,
                              input=stdin,text=True,encoding='utf-8',timeout=30)

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

    def assert_installed_build_sources(self):
        """Every COPY input must be present and byte-identical to the real TAR."""
        dockerfile=(self.target/'deploy/direct-server/Dockerfile').read_text(encoding='utf-8')
        sources=[]
        for line in dockerfile.splitlines():
            fields=shlex.split(line)
            if fields and fields[0]=='COPY':
                sources.extend(value for value in fields[1:-1] if not value.startswith('--'))
        self.assertIn('src',sources)
        self.assertIn('delivery/AI_Doll_Operit.toolpkg',sources)
        with tarfile.open(ROOT/'delivery/AI_Doll_Server_v2.25.1.tar.gz','r:gz') as archive:
            for source in sources:
                self.assertTrue((self.target/source).exists(),source)
                members=[member for member in archive.getmembers() if member.isfile() and
                         (member.name==source or member.name.startswith(source.rstrip('/')+'/'))]
                self.assertTrue(members,source)
                for member in members:
                    self.assertEqual((self.target/member.name).read_bytes(),archive.extractfile(member).read(),member.name)

    def test_installed_build_sources_refresh_on_upgrade(self):
        first=self.run_install();self.assertEqual(first.returncode,0,first.stderr)
        self.assert_installed_build_sources()
        core=self.target/'src/ai_doll/core/version.py'
        phone=self.target/'delivery/AI_Doll_Operit.toolpkg'
        core.write_bytes(b'outdated core')
        phone.write_bytes(b'outdated phone package')
        personal=self.target/'personal-data';personal.mkdir()
        history=personal/'history.sqlite3';history.write_bytes(b'personal history sentinel')
        env_file=self.target/'deploy/direct-server/.env'
        env_file.write_text('DOLL_DOMAIN='+DOMAIN+'\nDOLL_MCP_PROFILE=history\n',encoding='utf-8',newline='\n')
        private=(self.target/'connection-private.txt').read_bytes()
        upgraded=self.run_install(domain=False)
        self.assertEqual(upgraded.returncode,0,upgraded.stderr)
        self.assert_installed_build_sources()
        self.assertEqual(history.read_bytes(),b'personal history sentinel')
        self.assertEqual((self.target/'connection-private.txt').read_bytes(),private)
        self.assertEqual(env_file.read_text(encoding='utf-8'),'DOLL_DOMAIN='+DOMAIN+'\nDOLL_MCP_PROFILE=history\n')

    def test_incomplete_source_does_not_replace_installed_core_or_phone(self):
        first=self.run_install();self.assertEqual(first.returncode,0,first.stderr)
        core=(self.target/'src/ai_doll/core/version.py').read_bytes()
        phone=(self.target/'delivery/AI_Doll_Operit.toolpkg').read_bytes()
        record=(self.target/'deployment-private.conf').read_bytes()
        source=self.root/'incomplete-source';source.mkdir()
        with tarfile.open(ROOT/'delivery/AI_Doll_Server_v2.25.1.tar.gz','r:gz') as archive:
            archive.extractall(source,filter='data')
        (source/'delivery/AI_Doll_Operit.toolpkg').unlink()
        self.script=source/'Install_Server.sh'
        incomplete=self.run_install(domain=False)
        self.assertNotEqual(incomplete.returncode,0)
        self.assertIn('代码包不完整',incomplete.stderr)
        self.assertIn('delivery/AI_Doll_Operit.toolpkg',incomplete.stderr)
        self.assertEqual((self.target/'src/ai_doll/core/version.py').read_bytes(),core)
        self.assertEqual((self.target/'delivery/AI_Doll_Operit.toolpkg').read_bytes(),phone)
        self.assertEqual((self.target/'deployment-private.conf').read_bytes(),record)

    def test_installed_entry_downloads_the_release_before_reinstalling(self):
        first=self.run_install();self.assertEqual(first.returncode,0,first.stderr)
        (self.target/'src/ai_doll/core/version.py').write_bytes(b'outdated core')
        (self.target/'delivery/AI_Doll_Operit.toolpkg').write_bytes(b'outdated phone package')
        self.script=self.target/'Install_Server.sh'
        result=self.run_install(domain=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assert_installed_build_sources()

    def test_build_fixture_rejects_missing_copy_source(self):
        first=self.run_install();self.assertEqual(first.returncode,0,first.stderr)
        (self.target/'delivery/AI_Doll_Operit.toolpkg').unlink()
        result=subprocess.run([str(BASH),'-c',
            'export PATH="$FIXTURE_PATH"; docker compose --project-directory "$1" up -d --build',
            'build-input-check',self.posix(self.target/'deploy/direct-server')],
            env=self.env,capture_output=True,text=True,encoding='utf-8',timeout=10)
        self.assertEqual(result.returncode,31,result.stderr)
        self.assertIn('Missing Docker COPY source: delivery/AI_Doll_Operit.toolpkg',result.stderr)

    def test_invalid_domain_and_unknown_directory_have_no_docker_actions(self):
        for domain in ('http://doll.test-domain.net','doll.test-domain.net:8443','https://doll.test-domain.net/mcp',
                       'https://user@doll.test-domain.net','https://doll.test-domain.net/?x=1',
                       'a..net','example.com','$(touch x).net'):
            result=self.run_install('--domain',domain)
            self.assertNotEqual(result.returncode,0)
        self.target.mkdir();sentinel=self.target/'other.txt';sentinel.write_text('other project')
        result=self.run_install();self.assertNotEqual(result.returncode,0)
        self.assertEqual(sentinel.read_text(),'other project');self.assertFalse(self.log.exists())

    def test_copied_https_home_url_installs_the_expected_host(self):
        result=self.run_install('--domain','  HTTPS://DOLL.TEST-DOMAIN.NET:443/  ')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.target/'deploy/direct-server/.env').read_text().strip(),'DOLL_DOMAIN='+DOMAIN)
        self.assertIn('https://'+DOMAIN+'/#connect=',result.stdout)

    def test_guided_input_retries_and_eof_has_no_system_changes(self):
        empty=self.run_install(domain=False)
        self.assertNotEqual(empty.returncode,0)
        self.assertIn('未读到域名',empty.stderr)
        self.assertFalse(self.log.exists())
        retry=self.run_install('--dry-run',domain=False,stdin='bad-address\nhttps://'+DOMAIN+'/\n')
        self.assertEqual(retry.returncode,0,retry.stderr)
        self.assertIn('重新填写',retry.stderr)
        self.assertIn('HTTPS https://'+DOMAIN,retry.stdout)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.log.exists())

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
        with tarfile.open(ROOT/'delivery/AI_Doll_Server_v2.25.1.tar.gz','r:gz') as archive:
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
            with opener.open(f'http://127.0.0.1:{port}/pairing.js',timeout=2) as response:
                script=response.read()
            self.assertIn(b'QrCode',script)
            self.assertIn(b'AIDollPairing',script)
            self.assertNotIn(b'cdn.jsdelivr',script)
        finally:
            if child.poll() is None:child.terminate()
            child.wait(timeout=5)


if __name__=='__main__':unittest.main()
