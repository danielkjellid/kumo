# kumo

One Hetzner server running every side project behind Caddy, each on its own
subdomain. SQLite databases live under `/data/sqlite` on the box and are
streamed to object storage by Litestream, so a lost server is rebuilt from
the bucket.

Three layers, each changing at its own pace:

| Layer | Where | Changes when |
|---|---|---|
| Server, bucket, secrets, sign-in, `Caddyfile` | `src/pulumi/`, one file per part | Almost never. |
| What runs | `compose.yml`, `litestream.yml` | A project is added or removed. |
| Images | Each project's `.github/workflows/image.yml` | Every merge to main. |

The box pulls new images itself every five minutes through `bin/deploy.sh`,
so project repos never need credentials for the server.

## The kumo CLI

`kumo` (in `src/cli/`) wraps the Pulumi config, so you never type a config
path. `.envrc` puts it on your PATH inside the repo, together with this repo's
Pulumi login. That needs `direnv allow` once and `uv sync` after a fresh
clone.

| Command | What it does |
|---|---|
| `kumo init` | Asks for every setting, one by one. Safe to rerun: Enter keeps what is set, and `--skip-set` only asks for what is missing. |
| `kumo commit` | Shows what would change, then applies it if you say yes. |
| `kumo provision list\|add\|remove` | Who may open which app, by email. |
| `kumo env list\|set\|unset` | Each app's environment variables. |
| `kumo secret list\|set` | Tokens and keys. Generated ones get a new random value. |
| `kumo ssh`, `status`, `logs` | A shell, `docker compose ps` or the logs on the box. |

Changes to settings, access or env only reach the box after `kumo commit`.
Edits made directly on the box are overwritten by the next one.

## First-time setup

1. Install `pulumi`, `uv`, `direnv` and the AWS CLI. The cleanup rule on the
   bucket is set with `aws` (see the `shortcut:` comment in
   `src/pulumi/s3.py`). Load your laptop key in the SSH agent.
2. In the Hetzner console, create an API token (read and write) and an Object
   Storage access key. On GitHub, create a classic token with `read:packages`
   so the box can pull the app images.
3. Register the sign-in with Google (Cloud console, APIs & Services,
   Credentials, OAuth client ID) and Microsoft (Entra admin center, App
   registrations, accounts in any organizational directory and personal
   Microsoft accounts). Both take the redirect URI
   `https://auth.yourdomain.com/dex/callback`. A Microsoft client secret
   expires after two years at most, so note the date.
4. `kumo init`. It asks for the above and for who gets access to the apps.
   It also creates the GitHub Actions deploy key if it's missing, and
   generates the cookie secret, the Dex client secret and each app's
   `SECRET_KEY`.
5. `kumo commit`. It creates the server and the bucket, waits for first
   boot, then writes the env files to the box. The `ipv4` output is the
   server's address.
6. Point a wildcard DNS record at it: `*.yourdomain.com A <ipv4>`.
7. In this repo's GitHub settings, add the secrets `DEPLOY_HOST` (the IPv4)
   and `DEPLOY_SSH_KEY` (the private half of `~/.ssh/infra-deploy`). Push to
   main.

The deploy workflow copies the config files over and runs `bin/deploy.sh`.
Cron runs the same script afterwards, so later image pushes need nothing
from you.

The bucket keeps every deleted backup file for 7 days under a compliance
object lock, so a key stolen from the box can't wipe the backups.

## Who gets in

Every app sits behind a Google or Microsoft sign-in. `kumo provision add
cadence someone@outlook.com` gives that account access to cadence. Signing in
needs a place on at least one app's list. Anyone else gets a 403 page after
signing in, and someone on another app's list sees "You don't have access to
this app." An app with no list lets no one in.

## Adding a project

The project needs a Dockerfile that runs migrations and serves on port 8000,
and a copy of `image.yml` from cadence or gatekeeper. Every request that
reaches the app carries the signed-in account in `X-Auth-Request-Email`,
which only Caddy can set, so the app may trust it. Then, here:

1. A service in `compose.yml`, copied from an existing one. For a SQLite app,
   point its database at `/data/sqlite/<name>.db`.
2. The same path in `litestream.yml`, and the name in the `restore` loop.
3. The name in `src/cli/apps.py`. Pulumi then adds its site to the
   `Caddyfile`, behind the sign-in.
4. `kumo env set <name> SECRET_KEY`, `kumo provision add <name> <email>` and
   `kumo commit`.

## How a deploy goes wrong, and where to look

- `kumo status` shows what is running. `restore` is a
  one-shot that should show exited with code 0.
- `kumo logs <service>` for an app that is restarting.
- Caddy fetches certificates on first request for a hostname. A new
  subdomain takes a few seconds the first time.
- The `restore` step fails if the bucket is unreachable, and the apps wait
  for it, so a broken backup setup stops the deploy instead of running
  without backups. Check the bucket settings in the stack config first.

## Restoring somewhere else

Any machine with the bucket credentials can rebuild a database:

```sh
litestream restore -config litestream.yml -o cadence.db /data/sqlite/cadence.db
```
