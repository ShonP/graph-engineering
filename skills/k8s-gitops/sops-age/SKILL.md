---
name: sops-age
description: Use when a Kubernetes Secret or any other secret file is committed to git encrypted with SOPS and age - writing or changing .sops.yaml creation rules, adding or removing an age recipient, rotating a data key after a compromise, decrypting in CI or a Taskfile, or reviewing a *.enc.yaml diff.
license: MIT
---

# SOPS + age

Targets **sops 3.13.3** and **age 1.3.2**. Both were run at authoring time, so the Verify recipes
below are transcripts rather than guesses. Check what your repository pins before relying on a
version-specific rule.

Sources (fetched 2026-09-10 with `curl -sSL`, all HTTP 200):
- https://getsops.io/docs/ - "SOPS: Secrets OPerationS"
- https://getsops.io/docs/usage/identities/config-file/ - "Config file | SOPS: Secrets OPerationS"
- https://getsops.io/docs/usage/identities/age/ - "Age | SOPS: Secrets OPerationS"
- https://getsops.io/docs/usage/common-operations/ - "Common operations | SOPS: Secrets OPerationS"
- https://getsops.io/docs/usage/key-management/ - "Key management | SOPS: Secrets OPerationS"
- https://getsops.io/docs/usage/advanced/ - "Advanced usage | SOPS: Secrets OPerationS"
- https://getsops.io/docs/reference/ - "References | SOPS: Secrets OPerationS"
- https://github.com/getsops/sops - "GitHub - getsops/sops: Simple and flexible tool for managing secrets"
- https://github.com/FiloSottile/age - "GitHub - FiloSottile/age: A simple, modern and secure encryption tool (and Go library) with small explicit keys, no config options, and UNIX-style composability"

**No key material appears anywhere in this skill.** No private key, and no recipient (real or
example), is reproduced below; where a key would go, the shape is described instead.

## When to apply

- Touching `.sops.yaml`, any `*.enc.yaml` / `*.sops.yaml`, or any Kubernetes `Secret` that is
  committed to git.
- Adding or removing an age recipient (a new operator, a new cluster, an offboarding).
- Rotating a data key, or responding to a key that may have leaked.
- Wiring `sops decrypt` into CI, a Taskfile, a Makefile or a container entrypoint.
- Reviewing a diff that adds an encrypted file, or that adds a plaintext file next to one.

`security-review` runs on every one of these changes; this skill does not replace it.

## Rules

### `.sops.yaml` and creation rules

- The file must be named exactly `.sops.yaml`. "Other names (i.e. `.sops.yml`) won't be
  automatically discovered by sops. You'll need to pass the `--config .sops.yml` option."
  (usage/identities/config-file)
- `creation_rules` "are evaluated sequentially, the first match wins". A rule with **no**
  `path_regex` is a catch-all that matches everything, so it belongs last or not at all.
  (usage/identities/config-file)
- `path_regex` is matched against the path of the file being encrypted **relative to the
  `.sops.yaml`**, and sops looks for `.sops.yaml` recursively **from the working directory, not
  from the directory of the file being encrypted** (upstream issue 242). A rule that works from
  the repo root can miss when the same command runs from a subdirectory.
  (usage/identities/config-file)
- The config file "is ignored when KMS or PGP parameters are passed on the SOPS command line or
  in environment variables". A stray `--age` or `SOPS_AGE_RECIPIENTS` silently overrides the
  reviewed policy. (usage/identities/config-file)
- A list of age recipients goes under `age:` in a creation rule, one comma-separated string or a
  YAML block scalar across lines. (usage/identities/age; usage/key-management)

### What gets encrypted

- By default sops encrypts **all values** of a YAML, JSON, ENV or INI file and leaves the keys in
  cleartext; this partial-encryption behaviour does not apply to BINARY files.
  (usage/common-operations)
- For Kubernetes Secrets use `encrypted_regex: ^(data|stringData)$`. The docs give exactly this
  example: it "will encrypt the values under the `data` and `stringData` keys ... It will not
  encrypt other values that help you to navigate the file, like `metadata` which contains the
  secrets' names." That readability is what lets kustomize, Argo CD and a human reviewer see
  which resource a file declares without decrypting it. (usage/common-operations)
- Semantics, precisely: `encrypted_regex` means "a value is encrypted if its key matches this
  regular expression. All other values are **not** encrypted." Comments are always encrypted.
  (reference, Settings)
- The six selectors `unencrypted_suffix`, `encrypted_suffix`, `unencrypted_regex`,
  `encrypted_regex`, `unencrypted_comment_regex`, `encrypted_comment_regex` "are mutually
  exclusive and cannot all be used in the same file"; at most one may be set.
  (usage/common-operations; reference)
- Unencrypted content still counts toward the file's MAC, so it cannot be edited outside sops
  without breaking the integrity check, unless `mac_only_encrypted: true` is set (default
  `false`). Prefer the default: it means an edit to `metadata` is caught.
  (usage/common-operations; reference)
- Keep the file extension stable. sops picks the store from the extension; a file encrypted as
  YAML must be decrypted as YAML, otherwise pass `--input-type` / `--output-type` explicitly.
  (reference, "Important information on types")

### The age key

- The private key never lives in the repo. Point sops at it with **`SOPS_AGE_KEY_FILE`**, or
  `SOPS_AGE_KEY`, or `SOPS_AGE_KEY_CMD` (a command that prints the key, which can read
  `SOPS_AGE_RECIPIENT` to choose one). Without an override sops reads
  `$XDG_CONFIG_HOME/sops/age/keys.txt`, falling back to `~/.config/sops/age/keys.txt` on Linux
  and `~/Library/Application Support/sops/age/keys.txt` on macOS. (usage/identities/age)
- **House security rule, docs silent.** Prefer `SOPS_AGE_KEY_FILE` (a path) over `SOPS_AGE_KEY`
  (the key itself in the environment): a path does not land in a shell history or in a CI job log
  that dumps `env`. In Kubernetes that path is a mounted Secret volume, and any container reading
  it takes the value from a `secretKeyRef` or the mount. The SOPS docs list `SOPS_AGE_KEY_FILE`,
  `SOPS_AGE_KEY` and `SOPS_AGE_KEY_CMD` as three equal overrides and state no preference between
  them (usage/identities/age); the preference here is this plugin's, not the vendor's.
- The key file is a list of age X25519 identities, one per line, `#` comments ignored, each tried
  in sequence until one decrypts. So a single file can hold an operator key and a break-glass
  key. (usage/identities/age)
- `age-keygen -o key.txt` prints the **public** key on stdout and writes the private key to the
  file. Only the `age1...` public half belongs in `.sops.yaml`; `age-keygen -y key.txt` derives
  the public half from an existing key file. (github.com/FiloSottile/age)
- Post-quantum identities (`age-keygen -pq`, identities `AGE-SECRET-KEY-PQ-1...`, recipients
  `age1pq1...` at roughly 2000 characters) are built in from age **v1.3.0** and later, so they are
  available at the pinned 1.3.2. Recipient length is the practical cost.
  (github.com/FiloSottile/age)
- A key file can itself be passphrase-encrypted (`age-keygen | age -p > key.age`); sops and age
  detect and decrypt it. (github.com/FiloSottile/age)

### Adding, removing and rotating recipients

- After changing the recipient list in `.sops.yaml`, run **`sops updatekeys <file>`** on every
  affected file. "The SOPS team recommends the `updatekeys` approach" over command-line flags or
  hand-editing. It prompts with the diff; `-y` disables the prompt for CI.
  (usage/key-management)
- `updatekeys` adds or removes access to the existing data key. `sops rotate` generates a **new**
  data key and re-encrypts every value with it; `-i` / `--in-place` writes back. Use `updatekeys`
  when adding a key without rotating the data key. (usage/key-management)
- After a compromised key, the order is fixed: remove the key from `.sops.yaml`, then
  `sops updatekeys <file>`, **then** `sops rotate --in-place <file>`, then commit, and only then
  rotate the underlying passwords and API keys. "If done in the wrong order, the compromised key
  could still have access to the data in some cases", and new credentials introduced before the
  rotation completes are exposed to it too. (usage/key-management)
- Rotate the data key periodically, not only after an incident. (usage/key-management)
- Removing a key without rotating leaves the holder of the removed key with the data key they
  already saw. (usage/key-management, Direct Editing)

### Decrypting from scripts and CI

- Pipe, do not spill. "The best way to avoid [writing plaintext to disk] is to pass data to SOPS
  via stdin, and to let SOPS write data to stdout." `encrypt` and `decrypt` already write to
  stdout when no output file is given. (usage/advanced)
- With no filename, sops cannot infer the format and defaults to the binary store, "which is
  often not what you want". On stdin pass `--filename-override <path>` (which also selects the
  creation rule) or an explicit `--input-type` / `--output-type`. (usage/advanced; reference)
- `sops decrypt --extract '["data"]["key"]'` pulls a single value without materialising the whole
  plaintext document. (usage/common-operations)
- **Measured, not cited: no SOPS or age page discusses `argv`.** A secret value belongs in an
  environment variable via `secretKeyRef`, or on stdin, never as a command-line argument. Proved
  on macOS 25.5 at authoring time: `exec -a "tool --token=<value>" sleep 4 &` followed by
  `ps -o args= -p $!` from an unrelated shell printed `tool --token=<value>` verbatim. The same
  value piped on stdin never entered the receiving process's `argv`. On Linux the same exposure is
  `/proc/<pid>/cmdline`, which is world-readable by default. `argv` also lands in shell history
  and in CI logs.
- **House rule, docs silent.** Keep one canary encrypted file that CI decrypts on every run: it
  is the assertion that catches a decrypt pipeline which has quietly stopped producing Secrets. A
  pruned Secret can leave a GitOps Application both Synced and Healthy, so a green sync is not
  evidence that decryption still works. Neither the SOPS nor the age docs discuss pipeline
  liveness; this comes from operating the pattern.

## Anti-patterns

- **A secret file that matches no `creation_rules` entry.** sops has nothing to apply, and the
  file is committed in plain text with no error. Result: a credential in git history, which is a
  rotation, not a deletion.
- **Encrypting `metadata`, `kind` or `apiVersion`.** kustomize and Argo CD can no longer tell
  what the resource is, and no reviewer can read the diff. Use
  `encrypted_regex: ^(data|stringData)$`.
- **The age private key in the repo, in a Taskfile, in a container image, in a CI variable that
  gets echoed, or in a screenshot or terminal recording.** Anything holding `AGE-SECRET-KEY-1...`
  is the whole vault. Result: every encrypted file in every branch is readable forever.
- **`sops -d` redirected into a tracked file.** `sops decrypt secret.enc.yaml > secret.yaml`
  inside the worktree is one `git add .` away from a plaintext commit. Decrypt to stdout, to a
  pipe, or to a path outside the repo.
- **A secret passed as a command-line argument.** Visible in `ps`, in `/proc/<pid>/cmdline`, in
  shell history and in CI logs. Use `secretKeyRef` or stdin.
- **A catch-all `creation_rules` entry above the specific ones.** First match wins, so the
  catch-all swallows every file and the specific recipients are never applied.
- **Changing recipients without `sops updatekeys`.** `.sops.yaml` only governs **new** files;
  existing files keep the old recipient set until updated. Result: the offboarded key still
  decrypts, and the new operator cannot.
- **`sops rotate` before `sops updatekeys` after a compromise.** The documented order is the
  opposite. Result: the compromised key can still reach the data.
- **A `.sops.yml` (one `l`) config.** Not discovered; encryption silently uses no rule.

## Verify

Run from the repo root with the key file exported by path:

```bash
export SOPS_AGE_KEY_FILE=/path/outside/the/repo/age.key   # never a path inside the worktree
F=<path>/<name>.enc.yaml                                  # the canary, or any encrypted file
```

1. **The ciphertext is still navigable** (no decryption, so safe anywhere):

```bash
yq '.kind, .metadata.name, .metadata.namespace' "$F"
```

Prints `Secret`, the name and the namespace. If any of these come back as `ENC[...]`, the
`encrypted_regex` is too broad.

2. **The values really are encrypted:**

```bash
yq '.stringData.canary' "$F" | head -c 20
```

Prints `ENC[AES256_GCM,data:`. Anything else is a plaintext secret in git.

3. **Decryption works, without printing any value:**

```bash
sops decrypt "$F" | yq '.kind + "/" + .metadata.name'      # -> Secret/<name>
sops decrypt --extract '["stringData"]["canary"]' "$F" >/dev/null && echo ok
```

4. **No private key material is tracked:**

```bash
git grep -nE 'AGE-SECRET-KEY(-PQ)?-1' -- . ; echo "exit=$?"   # expect exit=1, no output
git ls-files .secrets/                                        # expect no output
git check-ignore -v .secrets/                                 # expect a .gitignore hit
```

5. **After a recipient change,** on every affected file:

```bash
sops updatekeys --yes "$F"       # then `sops rotate --in-place "$F"` if a key was removed
```

6. **Versions,** when a rule here looks wrong:

```bash
sops --version   # sops 3.13.3
age --version    # v1.3.2
```
