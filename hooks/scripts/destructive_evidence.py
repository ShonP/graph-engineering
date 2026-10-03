"""Evidence for the destructive-command guard; see guard-destructive.sh.

Reads a PreToolUse(Bash) payload on stdin and prints one permission `ask` for
the first segment of tool_input.command that matches a rule, or nothing. Rules:
R1 git remote remove|rm; R2 git push forced without a lease; R3 docker volume
rm|prune and docker system prune -a|--all|--volumes; R4 recursive rm on a
protected target. Evidence is local state only (git refs, `docker volume ls`),
2 s per probe. Silent in bypassPermissions mode. Stdlib only; never denies,
never allows, never writes a file.
"""
import json
import os
import re
import shlex
import subprocess
import sys

PARSE_REASON = 'could not parse this command; it matches a destructive pattern'
# Global options may sit between the tool and its subcommand: git -C <dir> push.
TRIGGER = re.compile(r'(?:^|[\s;&|(`/])(?:git\s(?:[^;&|`\n]*\s)?(?:push|remote)\b|rm\s'
                     r'|docker\s(?:[^;&|`\n]*\s)?(?:volume|system)\b)')
PUNCT = ';&|()<>`'
ASSIGN = re.compile(r'[A-Za-z_][A-Za-z0-9_]*=')
HEREDOC = re.compile(r'(?<!<)<<(?!<)(-?)[ \t]*([\'"]?)([A-Za-z_][\w.-]*)\2')
USERINFO = re.compile(r'(https?://)[^/@\s]+@')
WRAPPERS = ('sudo', 'command', 'env')
PUSH_VALUE_OPTS = ('-o', '--push-option', '--repo', '--receive-pack', '--exec')
DOCKER_VALUE_OPTS = ('-H', '--host', '-c', '--context', '--config', '-l', '--log-level',
                     '--tlscacert', '--tlscert', '--tlskey')
HOME = os.path.realpath(os.path.expanduser('~'))
DOCKER_DIRS = [os.path.realpath(os.path.expanduser(p))
               for p in ('/var/lib/docker', '~/.docker', '~/Library/Containers/com.docker.docker')]


def run(argv):
    """stdout of a local, read-only probe, or None when it fails or times out."""
    env = {k: v for k, v in os.environ.items() if k not in ('GIT_DIR', 'GIT_WORK_TREE')}
    try:
        done = subprocess.run(argv, capture_output=True, text=True, errors='replace',
                              timeout=2, stdin=subprocess.DEVNULL, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def git(cwd, *args):
    return run(['git', '-C', cwd, *args]) or None


def show(text):
    """One printable line with URL credentials masked: it lands in a terminal prompt."""
    return ''.join(ch if ch.isprintable() else '?' for ch in USERINFO.sub(r'\1***@', text))[:300]


def flatten(cmd):
    """Join line continuations, drop heredoc bodies, turn unquoted newlines into ';'."""
    out, i, quote, pending = [], 0, '', []
    while i < len(cmd):
        c, step = cmd[i], 1
        if c == '\\' and quote != "'":
            c, step = ('' if cmd.startswith('\n', i + 1) else cmd[i:i + 2]), 2
        elif quote:
            quote = '' if c == quote else quote
        elif c in '\'"':
            quote = c
        elif c == '\n':
            c, i, step = ' ; ', i + 1, 0
            for strip_tabs, delim in pending:
                hit = re.compile('(?m)^' + ('\t*' if strip_tabs else '') + re.escape(delim) + '$').search(cmd, i)
                i = hit.end() + 1 if hit else len(cmd)
            pending = []
        elif m := HEREDOC.match(cmd, i):
            pending.append((m.group(1) == '-', m.group(3)))
            c, step = ' ', m.end() - i
        out.append(c)
        i += step
    if quote:
        raise ValueError('No closing quotation')
    return ''.join(out)


def split(cmd):
    """Segments on && || ; | & ( ), backticks and newlines, each shlex-split. A
    redirection also ends a segment; its target then reads as a command name,
    which no rule matches."""
    lex = shlex.shlex(flatten(cmd), posix=True, punctuation_chars=PUNCT)
    lex.whitespace_split, lex.commenters = True, ''
    segs, seg = [], []
    for tok in list(lex):
        if tok and all(ch in PUNCT for ch in tok):
            segs.append(seg)
            seg = []
        else:
            seg.append(tok)
    return [s for s in segs + [seg] if s]


def unwrap(seg):
    """Drop leading VAR=value tokens and a leading sudo, command or env with its flags."""
    i = 0
    while i < len(seg):
        if ASSIGN.match(seg[i]):
            i += 1
        elif os.path.basename(seg[i]) in WRAPPERS:
            i += 1
            while i < len(seg) and seg[i].startswith('-'):
                i += 1
        else:
            break
    return seg[i:]


def resolve(path, cwd):
    for home in ('~', '$HOME', '${HOME}'):
        if path == home or path.startswith(home + '/'):
            path = HOME + path[len(home):]
    return os.path.realpath(os.path.join(cwd, path))


def short_flag(arg, letters):
    return arg.startswith('-') and not arg.startswith('--') and bool(set(arg[1:]) & set(letters))


def remote_rule(name, cwd):
    url = git(cwd, 'remote', 'get-url', name)
    name, shown = show(name), show(url) if url else 'url unknown'
    return f'removes git remote {name} ({shown}); recover with: git remote add {name} {shown if url else "<url>"}'


def push_rule(args, cwd):
    force = lease = False
    pos, it = [], iter(args)
    for a in it:
        if a in PUSH_VALUE_OPTS:
            next(it, None)
        elif a.startswith(('--force-with-lease', '--force-if-includes')):
            lease = True
        elif a == '--force' or short_flag(a, 'f'):
            force = True
        elif not a.startswith('-'):
            pos.append(a)
    specs = pos[1:]
    if lease or not (force or any(s.startswith('+') for s in specs)):
        return None
    branch = git(cwd, 'symbolic-ref', '--short', '-q', 'HEAD')
    remote = pos[0] if pos else (branch and git(cwd, 'config', f'branch.{branch}.remote')) or 'origin'
    spec = next((s for s in specs if s.startswith('+')), specs[0] if specs else '')
    src, _, dst = spec.lstrip('+').partition(':')
    if not spec:
        src, dst = 'HEAD', (branch and git(cwd, 'config', f'branch.{branch}.merge')) or branch or 'HEAD'
    dst = (dst or src).removeprefix('refs/heads/')
    local = git(cwd, 'rev-parse', '--verify', '-q', '--short=7', f'{src or "HEAD"}^{{commit}}')
    known = git(cwd, 'rev-parse', '--verify', '-q', '--short=7', f'refs/remotes/{remote}/{dst}^{{commit}}')
    return (f'force push without --force-with-lease to {show(remote)} {show(dst)} '
            f'(local {local or "unknown"}, last known remote {known or "unknown"})')


def git_rule(args, cwd):
    i = 0
    while i < len(args) and args[i].startswith('-'):
        if args[i] in ('-C', '-c') and i + 1 < len(args):
            cwd = resolve(args[i + 1], cwd) if args[i] == '-C' else cwd
            i += 1
        i += 1
    sub, rest = args[i:i + 1], args[i + 1:]
    if sub == ['remote'] and rest[:1] in (['remove'], ['rm']) and len(rest) > 1:
        return remote_rule(rest[1], cwd)
    return push_rule(rest, cwd) if sub == ['push'] else None


def docker_rule(args, _cwd):
    i = 0
    while i < len(args) and args[i].startswith('-'):
        i += 2 if args[i] in DOCKER_VALUE_OPTS else 1
    sub, rest = args[i:i + 1], args[i + 1:]
    volumes = sub == ['volume'] and rest[:1] in (['rm'], ['remove'], ['prune'])
    volumes = volumes or (sub == ['system'] and rest[:1] == ['prune'] and any(
        a in ('--all', '--volumes') or short_flag(a, 'a') for a in rest[1:]))
    if not volumes:
        return None
    listed = run(['docker', 'volume', 'ls', '-q'])
    return f'deletes Docker volumes ({"docker unavailable" if listed is None else f"{len(listed.split())} present"})'


def label(path):
    """Why a resolved path must not be deleted recursively, or None."""
    checks = ((path == '/', 'filesystem root'), (path == HOME, 'home directory'),
              (os.path.basename(path) == '.git', 'git metadata directory'),
              (path in DOCKER_DIRS, 'Docker data directory'),
              (os.path.lexists(os.path.join(path, '.git')), 'repository root'),
              (HOME.startswith(path + '/'), 'contains the home directory'),
              (any(p.startswith(path + '/') for p in DOCKER_DIRS), 'contains Docker data'))
    return next((why for hit, why in checks if hit), None)


def rm_rule(args, cwd):
    recursive, targets, options = False, [], True
    for a in args:
        if options and a == '--':
            options = False
        elif options and len(a) > 1 and a.startswith('-'):
            recursive = recursive or a == '--recursive' or short_flag(a, 'rR')
        elif a:
            targets.append(a)
    for target in targets if recursive else []:
        head, tail = os.path.split(target)
        if set('*?[') & set(tail):  # a glob: judge the directory it expands in
            path = resolve(head or '.', cwd)
            why, shown = label(path), os.path.join(path, tail)
            why = why if why is None or why.startswith('contains') else f'everything in the {why}'
        else:
            shown = resolve(target, cwd)
            why = label(shown)
        if why:
            return f'recursive delete of {show(shown)} ({why})'
    return None


def evaluate(command, cwd):
    for seg in split(command):
        seg = unwrap(seg)
        name, args = (os.path.basename(seg[0]), seg[1:]) if seg else ('', [])
        if name == 'cd':
            dirs = [a for a in args if not a.startswith('-')]
            cwd = resolve(dirs[0], cwd) if dirs else (cwd if args else HOME)
            continue
        rule = {'git': git_rule, 'docker': docker_rule, 'rm': rm_rule}.get(name)
        reason = rule(args, cwd) if rule else None
        if reason:
            return reason
    return None


def main():
    try:
        payload = json.loads(sys.stdin.read())
        command, cwd = payload['tool_input']['command'], payload.get('cwd') or os.getcwd()
    except (ValueError, KeyError, TypeError, AttributeError):
        return
    if not isinstance(command, str) or not isinstance(cwd, str):
        return
    # A hook `ask` prompts even in bypass mode; the owner chose no prompts, so stand down.
    if payload.get('permission_mode') == 'bypassPermissions':
        return
    try:
        reason = evaluate(command, cwd)
    except Exception:  # an unreadable command that looks destructive is what we ask about
        reason = PARSE_REASON if TRIGGER.search(command) else None
    if reason:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse', 'permissionDecision': 'ask',
            'permissionDecisionReason': f'graph-engineering guard: {reason}. Approve only if this is intended.'}}))


if __name__ == '__main__':
    main()
