#!/usr/bin/env python3
"""Unattended ARBITER skill install and public deployment using existing Mac credentials.

No login commands, passwords, prompts or dashboard steps. Existing engine, MCP
services, named tunnels and unrelated GitHub repositories are never modified.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import plistlib
import shutil
import tempfile
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

SOURCE = Path(__file__).resolve().parent
HOME = Path.home()
RUNTIME = HOME / 'Library' / 'Application Support' / 'ARBITER' / 'AgentSkill'
LOGS = RUNTIME / 'logs'
LAUNCH = HOME / 'Library' / 'LaunchAgents'
PORT = 9433
SERVER_LABEL = 'fyi.grip.arbiter.agent-skill.web'
TUNNEL_LABEL = 'fyi.grip.arbiter.agent-skill.tunnel'
TUNNEL_NAME = 'arbiter-agent-skill-grip'
GITHUB_REPO = 'arbiter-agent-skill'
RELEASE_VERSION = '1.2.0'


def run(cmd, timeout=40, cwd=None):
    """All external operations are explicitly noninteractive, including git/SSH."""
    environment = os.environ.copy()
    environment.update({
        'GIT_TERMINAL_PROMPT': '0',
        'GCM_INTERACTIVE': 'Never',
        'GH_PROMPT_DISABLED': '1',
        'SSH_ASKPASS_REQUIRE': 'never',
        'CLOUDFLARED_NO_AUTOUPDATE': 'true',
    })
    # Honor an existing SSH configuration and ssh-agent, but never request a password.
    environment.setdefault('GIT_SSH_COMMAND', 'ssh -o BatchMode=yes -o ConnectTimeout=8')
    try:
        return subprocess.run([str(x) for x in cmd], cwd=cwd, capture_output=True,
                              text=True, timeout=timeout, check=False, input='', env=environment)
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(cmd, 127, '', str(error))


def note(label, detail):
    print(f'{label:<16} {detail}', flush=True)


def copy_bundle():
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    if SOURCE.resolve() == RUNTIME.resolve():
        return
    tmp = RUNTIME.parent / ('.AgentSkill-install-' + str(os.getpid()))
    if tmp.exists():
        shutil.rmtree(tmp)
    def filt(_, names):
        return [n for n in names if n in {'.git', '__pycache__', '.DS_Store', 'logs'}]
    shutil.copytree(SOURCE, tmp, ignore=filt)
    if RUNTIME.exists():
        backup = RUNTIME.parent / ('AgentSkill.previous-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        RUNTIME.rename(backup)
        note('Backup', str(backup))
    tmp.rename(RUNTIME)
    note('Bundle', str(RUNTIME))


def install_skill():
    src = RUNTIME / 'skills' / 'arbiter'
    for target in (HOME / '.agents/skills/arbiter', HOME / '.claude/skills/arbiter'):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            if target.resolve() == src.resolve():
                note('Already linked', str(target))
                continue
            target.unlink()  # Only this specific skill path, no recursive foreign deletion.
        elif target.exists():
            backup = target.with_name('arbiter.previous-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
            target.rename(backup)
            note('Skill backup', str(backup))
        target.symlink_to(src, target_is_directory=True)
        note('Installed', str(target))


def port_health():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/healthz', timeout=2) as r:
            return r.status == 200 and json.loads(r.read()).get('skill') == 'arbiter'
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return False


def make_launch_agent(label, cmd, environ=None):
    LAUNCH.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    plist = LAUNCH / (label + '.plist')
    options = {'Label': label, 'ProgramArguments': [str(x) for x in cmd],
               'WorkingDirectory': str(RUNTIME), 'RunAtLoad': True,
               'KeepAlive': True,
               'StandardOutPath': str(LOGS / (label + '.out.log')),
               'StandardErrorPath': str(LOGS / (label + '.err.log'))}
    if environ:
        options['EnvironmentVariables'] = environ
    with plist.open('wb') as fd:
        plistlib.dump(options, fd)
    domain = f'gui/{os.getuid()}'
    # Only boot out this package's known service label; never touch other launch agents.
    run(['launchctl', 'bootout', f'{domain}/{label}'], timeout=12)
    start = run(['launchctl', 'bootstrap', domain, str(plist)], timeout=20)
    if start.returncode:
        note('LaunchAgent', f'{label}: bootstrap error: {(start.stderr or start.stdout).strip()}')
        return False
    run(['launchctl', 'kickstart', '-k', f'{domain}/{label}'], timeout=12)
    note('LaunchAgent', f'{label}: loaded')
    return True


def start_local_site(host):
    if sys.platform != 'darwin':
        note('Local host', 'launchd deployment requires macOS; files installed only')
        return False
    python = shutil.which('python3') or sys.executable
    start = make_launch_agent(SERVER_LABEL, [python, str(RUNTIME / 'site.py'), '--port', str(PORT)],
                              {'ARBITER_SKILL_HOST': host})
    if start:
        for _ in range(12):
            if port_health():
                note('Site health', f'OK http://127.0.0.1:{PORT}/healthz')
                return True
            time.sleep(.35)
    note('Site health', 'not confirmed; see ' + str(LOGS))
    return False


def tunnel_uuid(cloudflared):
    listing = run([cloudflared, 'tunnel', 'list', '--output', 'json'], timeout=35)
    if listing.returncode:
        note('Cloudflare', 'cannot list tunnels: ' + (listing.stderr or listing.stdout).strip()[:240])
        return None, False
    try:
        data = json.loads(listing.stdout)
        for item in data:
            if item.get('name') == TUNNEL_NAME:
                return item.get('id'), True
    except (ValueError, TypeError):
        note('Cloudflare', 'tunnel list did not return JSON')
        return None, False
    created = run([cloudflared, 'tunnel', 'create', TUNNEL_NAME], timeout=45)
    if created.returncode:
        note('Cloudflare', 'create failed: ' + (created.stderr or created.stdout).strip()[:260])
        return None, False
    listing = run([cloudflared, 'tunnel', 'list', '--output', 'json'], timeout=35)
    try:
        for item in json.loads(listing.stdout):
            if item.get('name') == TUNNEL_NAME:
                return item.get('id'), True
    except (ValueError, TypeError):
        pass
    note('Cloudflare', 'tunnel created but its UUID could not be read')
    return None, False


def discover_tunnel_credentials(tunnel_id):
    """Find pre-existing named-tunnel credentials without prompting or moving keys."""
    roots = [HOME / '.cloudflared',
             HOME / 'Library' / 'Application Support' / 'cloudflared',
             HOME / 'Library' / 'Application Support' / 'Cloudflare',
             Path('/opt/homebrew/etc/cloudflared'),
             Path('/usr/local/etc/cloudflared'),
             Path('/etc/cloudflared')]
    for root in roots:
        if not root.is_dir():
            continue
        direct = root / (tunnel_id + '.json')
        if direct.is_file():
            return direct
        for f in root.glob('*.json'):
            try:
                doc = json.loads(f.read_text())
                if str(doc.get('TunnelID', '')).lower() == tunnel_id.lower():
                    return f
            except (ValueError, OSError, UnicodeError, AttributeError):
                continue
    return None


def public_probe(url, timeout=5):
    """Check actual public route with response classification and bounded diagnostics."""
    request = urllib.request.Request(url, headers={
        'User-Agent': 'ARBITER-skill-verifier/1.2',
        'Accept': 'text/plain, text/markdown, */*'
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(8192)
            if response.status == 200 and b'name: arbiter' in body and b'---' in body:
                return True, 'HTTP 200 (ARBITER skill content confirmed)'
            return False, 'HTTP ' + str(response.status) + ' (unexpected document)'
    except urllib.error.HTTPError as exc:
        body = exc.read(2048).decode('utf-8', 'replace')
        import re
        match = re.search(r'(?:Error\s*|error code[:\s]*)(10[0-9]{2}|5[0-9]{2})', body, flags=re.I)
        suffix = (' / Cloudflare ' + match.group(1)) if match else ''
        return False, f'HTTP {exc.code}{suffix}'
    except urllib.error.URLError as exc:
        return False, 'network/DNS/TLS: ' + str(exc.reason)[:130]
    except (TimeoutError, OSError) as exc:
        return False, type(exc).__name__ + ': ' + str(exc)[:130]


def launchd_summary(label):
    check = run(['launchctl', 'print', f'gui/{os.getuid()}/{label}'], timeout=8)
    if check.returncode:
        return 'service not running under user launchd'
    import re
    pid = re.search(r'^\s*pid = (\d+)', check.stdout, re.M)
    state = re.search(r'^\s*state = ([^\n]+)', check.stdout, re.M)
    return f'state={state.group(1).strip() if state else "unknown"}; pid={pid.group(1) if pid else "none"}'


def tunnel_diagnostics(cloudflared, tunnel, label=TUNNEL_LABEL):
    note('Tunnel status', launchd_summary(label))
    info = run([cloudflared, 'tunnel', 'info', tunnel], timeout=16)
    if info.returncode:
        note('Tunnel network', 'info unavailable: ' + (info.stderr or info.stdout).strip()[-180:])
    else:
        lines = info.stdout.splitlines()
        connected = [line for line in lines if 'conn' in line.lower() or 'edge' in line.lower()]
        note('Tunnel network', ('; '.join(connected) if connected else 'tunnel info returned successfully')[:240])
    logfile = LOGS / (label + '.err.log')
    if logfile.is_file():
        # Log output is limited and kept on the owner's Mac; never published to GitHub.
        try:
            tail = logfile.read_text(errors='replace')[-10000:]
            signals = [line.strip() for line in tail.splitlines()
                       if any(term in line.lower() for term in
                              ('err ', 'error=', 'failed', 'registered tunnel', 'reconnecting', 'quic'))]
            if signals:
                note('Tunnel log', signals[-1][-260:])
        except OSError:
            pass


def verify_public_skill(host, cloudflared=None, tunnel=None, wait_seconds=95):
    """Allow connector registration and DNS propagation; inspect cause if still failing."""
    url = f'https://{host}/skills/arbiter/SKILL.md'
    deadline = time.monotonic() + wait_seconds
    previous = None
    attempt = 0
    while True:
        attempt += 1
        ok, detail = public_probe(url)
        if ok:
            note('Public HTTPS', 'VERIFIED ' + url)
            note('HTTP check', detail)
            return True
        if detail != previous:
            note('HTTP check', detail + f' (attempt {attempt})')
            previous = detail
        if time.monotonic() >= deadline:
            break
        time.sleep(min(4, max(0, deadline - time.monotonic())))
    note('Public HTTPS', 'NOT VERIFIED ' + url)
    if cloudflared and tunnel:
        tunnel_diagnostics(cloudflared, tunnel)
    note('Recovery', 'No manual login attempted; existing service and repository preserved')
    return False


def _ingress_validate(cloudflared, config, host):
    result = run([cloudflared, 'tunnel', '--config', str(config), 'ingress', 'validate'], timeout=12)
    if result.returncode:
        note('Ingress config', 'invalid: ' + (result.stderr or result.stdout).strip()[-220:])
        return False
    rule = run([cloudflared, 'tunnel', '--config', str(config),
                'ingress', 'rule', 'https://' + host + '/skills/arbiter/SKILL.md'], timeout=12)
    if rule.returncode or f'127.0.0.1:{PORT}' not in (rule.stdout + rule.stderr):
        note('Ingress config', 'route did not confirm origin localhost:' + str(PORT))
        return False
    note('Ingress config', 'validated ' + host + ' -> localhost:' + str(PORT))
    return True


def setup_cloudflare(host):
    cloudflared = shutil.which('cloudflared')
    if not cloudflared:
        note('Cloudflare', 'BLOCKED: cloudflared not found in existing executable paths')
        return False
    tunnel, ok = tunnel_uuid(cloudflared)
    if not ok or not tunnel:
        note('Cloudflare', 'BLOCKED: existing Cloudflare credentials did not provision named tunnel')
        return False
    creds = discover_tunnel_credentials(tunnel)
    if creds is None:
        note('Cloudflare', f'BLOCKED: no local named-tunnel credential for {tunnel}; no login attempted')
        return False
    config = RUNTIME / 'tunnel.yml'
    # A dedicated tunnel for documentation: no writes to pre-existing tunnels or ingress.
    config.write_text(f'tunnel: {tunnel}\ncredentials-file: "{creds}"\ningress:\n  - hostname: {host}\n    service: http://127.0.0.1:{PORT}\n  - service: http_status:404\n')
    if not _ingress_validate(cloudflared, config, host):
        return False
    dns = run([cloudflared, 'tunnel', 'route', 'dns', tunnel, host], timeout=40)
    if dns.returncode:
        msg = (dns.stderr or dns.stdout).strip()
        if 'already configured' in msg.lower() or 'already exists' in msg.lower():
            note('Cloudflare', 'Existing hostname DNS record detected; no overwrite')
        else:
            note('Cloudflare', 'DNS route failed: ' + msg[:260])
            return False
    else:
        note('Cloudflare', 'DNS route ensured: ' + host)
    if not make_launch_agent(TUNNEL_LABEL,
                             [cloudflared, 'tunnel', '--config', str(config), '--protocol', 'http2', 'run', tunnel]):
        return False
    note('Transport', 'http2 (no QUIC retry delay; dedicated skill tunnel only)')
    note('Tunnel status', launchd_summary(TUNNEL_LABEL))
    return verify_public_skill(host, cloudflared, tunnel)


def _git(commit_dir, *args, timeout=40):
    return run(['git', *args], cwd=commit_dir, timeout=timeout)


def _git_identity(repo, login, account_id):
    """Use the account's existing git identity or GitHub's verified noreply pattern."""
    name = _git(repo, 'config', '--get', 'user.name')
    email = _git(repo, 'config', '--get', 'user.email')
    if not name.stdout.strip():
        result = _git(repo, 'config', '--local', 'user.name', login)
        if result.returncode: return False
    if not email.stdout.strip():
        noreply = f'{account_id}+{login}@users.noreply.github.com' if account_id.isdigit() else f'{login}@users.noreply.github.com'
        result = _git(repo, 'config', '--local', 'user.email', noreply)
        if result.returncode: return False
    return True


def _copy_public_files(destination):
    """Export only versioned skill files; exclude credentials, tunnel.yml and logs."""
    include = ('README.md', 'LICENSE', 'site.py', 'deploy.py', '.gitignore')
    for name in include:
        shutil.copy2(RUNTIME / name, destination / name)
    for directory in ('skills', 'scripts', 'tests', '.github'):
        shutil.copytree(RUNTIME / directory, destination / directory, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
    (destination / '.arbiter-skill-managed').write_text('ARBITER AGENT SKILL - Actual General Intelligence, Inc.\n')


def setup_github():
    gh, git = shutil.which('gh'), shutil.which('git')
    if not gh or not git:
        note('GitHub', 'BLOCKED: gh and git are required for automated repository creation')
        return False
    # The GitHub API uses existing gh credentials; git uses existing SSH/keychain.
    me = run([gh, 'api', 'user', '--jq', '.login'], timeout=18)
    login = me.stdout.strip() if me.returncode == 0 else ''
    if not login:
        note('GitHub', 'BLOCKED: existing GitHub API authorization unavailable; no login attempted')
        return False
    uid = run([gh, 'api', 'user', '--jq', '.id'], timeout=18)
    account_id = uid.stdout.strip() if uid.returncode == 0 else ''
    name = f'{login}/{GITHUB_REPO}'
    check = run([gh, 'repo', 'view', name, '--json', 'name,visibility,url'], timeout=20)
    exists = check.returncode == 0
    with tempfile.TemporaryDirectory(prefix='arbiter-agent-skill-publish-') as work:
        repo = Path(work) / 'repo'
        if exists:
            # Clone through the user's configured git SSH credentials, with no prompts.
            clone = run([git, 'clone', '--depth', '1', f'git@github.com:{name}.git', str(repo)], timeout=50)
            if clone.returncode:
                if repo.exists():
                    shutil.rmtree(repo)
                clone = run([gh, 'repo', 'clone', name, str(repo), '--', '--depth', '1'], timeout=50)
            if clone.returncode:
                note('GitHub', 'BLOCKED: existing repository could not be cloned noninteractively: ' + (clone.stderr or clone.stdout).strip()[:190])
                return False
            marker = repo / '.arbiter-skill-managed'
            if not marker.is_file() or not any(text in marker.read_text() for text in ('ARBITER AGENT SKILL', 'Managed by ARBITER Agent Skill')):
                note('GitHub', f'BLOCKED: {name} exists but is not identified as this managed skill; left untouched')
                return False
            # Only these known project paths are changed, leaving unrelated repository files alone.
            for directory in ('skills', 'scripts', 'tests', '.github'):
                target = repo / directory
                if target.exists():
                    shutil.rmtree(target)
        else:
            repo.mkdir()
            init = _git(repo, 'init', '-b', 'main')
            if init.returncode:
                note('GitHub', 'BLOCKED: git init failed: ' + init.stderr.strip()[:190])
                return False
        _copy_public_files(repo)
        if not _git_identity(repo, login, account_id):
            note('GitHub', 'BLOCKED: git author setup failed')
            return False
        _git(repo, 'add', '--', 'README.md', 'LICENSE', 'site.py', 'deploy.py',
             '.gitignore', '.arbiter-skill-managed', 'skills', 'scripts', 'tests', '.github')
        changes = _git(repo, 'status', '--porcelain')
        if changes.returncode:
            note('GitHub', 'BLOCKED: unable to check project changes')
            return False
        if not changes.stdout.strip() and exists:
            note('GitHub', 'UP TO DATE https://github.com/' + name)
            return True
        commit = _git(repo, 'commit', '-m', 'Publish ARBITER agent skill release 1.2.0', timeout=25)
        if commit.returncode:
            note('GitHub', 'BLOCKED: git commit failed: ' + commit.stderr.strip()[:190])
            return False
        if exists:
            branch = _git(repo, 'branch', '--show-current')
            current = branch.stdout.strip() if branch.returncode == 0 else ''
            if not current:
                note('GitHub', 'BLOCKED: cannot identify existing repository branch')
                return False
            push = _git(repo, 'push', 'origin', 'HEAD:' + current, timeout=60)
        else:
            push = run([gh, 'repo', 'create', name, '--public', '--source', str(repo),
                        '--remote', 'origin', '--push'], timeout=90)
        if push.returncode:
            note('GitHub', 'BLOCKED: publication failed: ' + (push.stderr or push.stdout).strip()[:280])
            return False
        verified = run([gh, 'api', f'repos/{name}', '--jq', '.html_url'], timeout=20)
        if verified.returncode or not verified.stdout.strip():
            note('GitHub', 'push completed but GitHub publication not independently verified')
            return False
        note('GitHub', 'PUBLISHED ' + verified.stdout.strip())
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.getenv('ARBITER_SKILL_HOST', 'arbiter-skill.grip.fyi'))
    parser.add_argument('--no-cloudflare', action='store_true')
    parser.add_argument('--no-github', action='store_true')
    parser.add_argument('--no-server', action='store_true')
    args = parser.parse_args()
    if not args.host.endswith('.grip.fyi') or any(ch for ch in args.host if ch not in 'abcdefghijklmnopqrstuvwxyz0123456789-.'):
        parser.error('host must be a simple *.grip.fyi DNS hostname')
    print('\nARBITER / AGENT SKILL / RELEASE 1.2.0 / UNATTENDED\n')
    check = run([sys.executable, str(SOURCE / 'scripts/validate_release.py')])
    if check.returncode:
        print(check.stdout, check.stderr)
        return 2
    note('Validation', check.stdout.strip())
    copy_bundle()
    install_skill()
    local = False if args.no_server else start_local_site(args.host)
    public = False
    if not args.no_cloudflare and local:
        public = setup_cloudflare(args.host)
    elif not args.no_cloudflare:
        note('Cloudflare', 'skipped because local service was not confirmed')
    github = False if args.no_github else setup_github()
    print('\nRESULT\n' + json.dumps({
        'client_skill_installed': True,
        'localhost_docs_confirmed': local,
        'public_https_verified': public,
        'github_published': github,
        'local_skill': str(RUNTIME / 'skills/arbiter/SKILL.md'),
        'public_skill_url': ('https://' + args.host + '/skills/arbiter/SKILL.md') if public else None,
        'engine_modified': False,
        'mcp_service_modified': False
    }, indent=2))
    incomplete = ((not args.no_server and not local) or
                  (not args.no_cloudflare and not public) or
                  (not args.no_github and not github))
    if incomplete:
        note('Release', 'INCOMPLETE: one or more required publication checks failed; no interactive action requested')
        return 3
    note('Release', 'COMPLETE: all requested publication checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
