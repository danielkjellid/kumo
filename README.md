# kumo

One Hetzner server running every side project behind Caddy, each on its own
subdomain. SQLite databases live under `/data/sqlite` on the box and are
streamed to object storage by Litestream, so a lost server is rebuilt from
the bucket.

Three layers, each changing at its own pace:

| Layer | Where | Changes when |
|---|---|---|
| Server, bucket, secrets | `pulumi/` | Almost never. |
| What runs | `compose.yml`, `Caddyfile`, `litestream.yml` | A project is added or removed. |
| Images | Each project's `.github/workflows/image.yml` | Every merge to main. |

The box pulls new images itself every five minutes through `bin/deploy.sh`,
so project repos never need credentials for the server.

## First-time setup

1. In the Hetzner console, create an API token (read and write) and an Object
   Storage access key. Pulumi creates the bucket itself. On GitHub, create a
   classic token with `read:packages` so the box can pull the app images.
2. Generate a deploy key for GitHub Actions:
   `ssh-keygen -t ed25519 -f ~/.ssh/infra-deploy -N "" -C github-deploy`.
3. Create the Pulumi stack in `pulumi/` and give it everything the box needs:

   ```sh
   cd pulumi
   pulumi stack init prod
   pulumi config set --secret hcloud:token <token>
   pulumi config set --path 'authorizedKeys[0]' "$(cat ~/.ssh/id_ed25519.pub)"
   pulumi config set --path 'authorizedKeys[1]' "$(cat ~/.ssh/infra-deploy.pub)"
   pulumi config set bucket <bucket-name>
   pulumi config set --secret s3AccessKey <access-key>
   pulumi config set --secret s3SecretKey <secret-key>
   pulumi config set domain <yourdomain.com>
   pulumi config set ghcrUser <github-user>
   pulumi config set --secret ghcrToken <github-token>
   pulumi config set --secret --path env.cadence.SECRET_KEY <secret>
   pulumi config set --secret --path env.gatekeeper.SECRET_KEY <secret>
   pulumi config set --path env.gatekeeper.DEBUG 0
   ```

   Each key under `env.<app>` becomes a line in `/srv/infra/env/<app>.env` on
   the box. Pulumi writes those files, `/srv/infra/.env` and
   `env/litestream.env` over SSH, so change them with `pulumi config set` and
   `pulumi up`, not on the box.

   The bucket keeps every deleted backup file for 7 days under a compliance
   object lock, so a key stolen from the box can't wipe the backups.

   `serverType` (default `cpx12`) and `location` (default `hel1`) are optional.
4. `pulumi up`, with your laptop key loaded in the SSH agent. It waits for
   the box to finish first boot before writing to it. The `ipv4` output is
   the server's address.
5. Point a wildcard DNS record at it: `*.yourdomain.com A <ipv4>`.
6. In this repo's GitHub settings, add the secrets `DEPLOY_HOST` (the IPv4)
   and `DEPLOY_SSH_KEY` (the private half of the deploy key). Push to main.

The deploy workflow copies the config files over and runs `bin/deploy.sh`.
Cron runs the same script afterwards, so later image pushes need nothing
from you.

## Adding a project

The project needs a Dockerfile that runs migrations and serves on port 8000,
and a copy of `image.yml` from cadence or gatekeeper. Then, here:

1. A service in `compose.yml`, copied from an existing one. For a SQLite app,
   point its database at `/data/sqlite/<name>.db`.
2. The same path in `litestream.yml`, and the name in the `restore` loop.
3. A block in `Caddyfile`.
4. The name in `APPS` in `pulumi/__main__.py`, its variables under
   `env.<name>` in the stack config, then `pulumi up`.

## How a deploy goes wrong, and where to look

- `docker compose ps` on the box shows what is running. `restore` is a
  one-shot that should show exited with code 0.
- `docker compose logs <service>` for an app that is restarting.
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
