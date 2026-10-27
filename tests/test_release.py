import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest import mock
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import site as stdlib_site # noqa: F401
import importlib.util
spec = importlib.util.spec_from_file_location('arbiter_site', ROOT / 'site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class TestSite(unittest.TestCase):
    def test_routes(self):
        for path in ('/', '/skills/arbiter/SKILL.md', '/agents.json', '/openapi.json', '/healthz'):
            data, mimetype = site.resolve(path)
            self.assertTrue(data)
            self.assertTrue(mimetype)
        self.assertIsNone(site.resolve('/.env')[0])
        self.assertIsNone(site.resolve('/skills/arbiter/scripts/arbiter_client.py')[0])
        self.assertIsNone(site.resolve('/skills/arbiter/../../../../../etc/passwd')[0])

    def test_metadata(self):
        doc = json.loads(site.resolve('/manifest.json')[0])
        self.assertEqual(doc['name'], 'arbiter')
        self.assertEqual(doc['mcp']['tools'], ['arbiter_compare', 'arbiter_embed'])
        spec = json.loads(site.resolve('/openapi.json')[0])
        self.assertEqual(len(spec['paths']), 2)


class MockApi(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        self.server.received = json.loads(self.rfile.read(length))
        if self.path == '/v1/compare':
            body = {'top': ['Rollback'], 'all': ['Rollback', 'Wait']}
            code = 200
        else:
            body = {'error': 'payment_required'}
            code = 402
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TestClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), MockApi)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_compare_and_402(self):
        url = 'http://127.0.0.1:' + str(self.server.server_port)
        for name, expected in [('compare', 0), ('embed', 4)]:
            run = subprocess.run([sys.executable, str(ROOT / 'skills/arbiter/scripts/arbiter_client.py'),
                                  name, '--base', url,
                                  '--file', str(ROOT / 'skills/arbiter/examples' / (name + '.json'))],
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, expected, run.stderr)
            self.assertIn('HTTP ' + ('200' if name == 'compare' else '402'), run.stdout)

    def test_dry_run_no_network(self):
        run = subprocess.run([sys.executable, str(ROOT / 'skills/arbiter/scripts/arbiter_client.py'),
                              'compare', '--file', str(ROOT / 'skills/arbiter/examples/compare.json'),
                              '--dry-run'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0)
        self.assertIn('v1/compare', run.stdout)


class TestDeploymentUnattended(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('arbiter_deploy', ROOT / 'deploy.py')
        cls.deploy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.deploy)

    def test_commands_disable_all_prompts(self):
        with mock.patch.object(self.deploy.subprocess, 'run') as execute:
            execute.return_value = subprocess.CompletedProcess(['git', 'status'], 0, '', '')
            response = self.deploy.run(['git', 'status'])
            self.assertEqual(response.returncode, 0)
            args, kwargs = execute.call_args
            self.assertEqual(kwargs['input'], '')
            self.assertEqual(kwargs['env']['GIT_TERMINAL_PROMPT'], '0')
            self.assertEqual(kwargs['env']['GH_PROMPT_DISABLED'], '1')
            self.assertEqual(kwargs['env']['GCM_INTERACTIVE'], 'Never')
            self.assertIn('BatchMode=yes', kwargs['env']['GIT_SSH_COMMAND'])

    def test_existing_cloudflared_credentials_discovered(self):
        with tempfile.TemporaryDirectory() as home:
            root = Path(home) / '.cloudflared'
            root.mkdir()
            uid = '00000000-1111-2222-3333-444444444444'
            secret = root / (uid + '.json')
            secret.write_text('test')
            with mock.patch.object(self.deploy, 'HOME', Path(home)):
                self.assertEqual(self.deploy.discover_tunnel_credentials(uid), secret)

    def test_nonmatching_cloudflared_secret_not_used(self):
        with tempfile.TemporaryDirectory() as home:
            root = Path(home) / '.cloudflared'
            root.mkdir()
            (root / 'other.json').write_text('{"TunnelID":"other-tunnel"}')
            with mock.patch.object(self.deploy, 'HOME', Path(home)):
                self.assertIsNone(self.deploy.discover_tunnel_credentials('11111111-2222-3333-4444-555555555555'))

    def test_git_stage_excludes_cloudflare_credentials(self):
        with tempfile.TemporaryDirectory() as home:
            root = Path(home) / 'installed'
            root.mkdir()
            for name in ('README.md', 'LICENSE', 'site.py', 'deploy.py', '.gitignore'):
                (root / name).write_text(name)
            for folder in ('skills', 'scripts', 'tests', '.github'):
                (root / folder).mkdir()
                (root / folder / 'file.txt').write_text(folder)
            (root / 'tunnel.yml').write_text('SECRET')
            (root / 'logs').mkdir()
            (root / 'logs' / 'debug.log').write_text('SECRET')
            dest = Path(home) / 'repo'
            dest.mkdir()
            with mock.patch.object(self.deploy, 'RUNTIME', root):
                self.deploy._copy_public_files(dest)
            self.assertTrue((dest / '.arbiter-skill-managed').is_file())
            self.assertFalse((dest / 'tunnel.yml').exists())
            self.assertFalse((dest / 'logs').exists())


if __name__ == '__main__':
    unittest.main()
