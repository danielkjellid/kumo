import json
import subprocess
from datetime import datetime, timezone

import click

from .apps import APPS
from .box import ssh_args
from .stack import load

# Prints the container, its image and the database file, split by @@ lines.
REMOTE = """cd /srv/infra
c=$(docker compose ps -aq {app})
if [ -n "$c" ]; then
  docker inspect "$c"; echo @@; docker image inspect "$(docker inspect -f '{{{{.Image}}}}' "$c")"
else
  echo '[]'; echo @@; echo '[]'
fi
echo @@; stat -c '%s %Y' /data/sqlite/{app}.db 2>/dev/null || true"""


@click.command()
@click.argument("app", type=click.Choice(APPS))
@click.pass_obj
def describe(stack_name: str, app: str) -> None:
    """Show where APP lives, who may open it, and how it is doing on the box."""
    config = load(stack_name)
    result = subprocess.run(
        ssh_args(stack_name) + [REMOTE.format(app=app)], capture_output=True, text=True, check=True
    )
    containers, images, db = result.stdout.split("@@\n")
    container = (json.loads(containers) or [None])[0]
    image = (json.loads(images) or [None])[0]

    click.echo(f"{app}  https://{app}.{config.get('domain')}")
    if container:
        state = container["State"]
        status = f"{state['Status']} for {ago(state['StartedAt'])}, {container['RestartCount']} restarts"
        built = image["Created"]
        click.echo(f"  status    {status}")
        click.echo(f"  image     built {ago(built)} ago, {commit(image, built)}")
    else:
        click.echo("  status    not created yet")
    if db.strip():
        size, changed = db.split()
        when = datetime.fromtimestamp(int(changed), timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        click.echo(f"  database  {int(size) / 1e6:.1f} MB, last written {ago(when)} ago")
    else:
        click.echo("  database  none yet")
    click.echo(f"  access    {', '.join(config.get(f'access.{app}') or ['nobody'])}")
    click.echo(f"  env       {', '.join(sorted(config.get(f'env.{app}') or {})) or 'none'}")


def commit(image: dict, built: str) -> str:
    """The app commit whose image build was running when this image was built."""
    # shortcut: matches on build time because the images carry no revision
    # label. Add org.opencontainers.image.revision in each app's image.yml to
    # read it straight off the image instead.
    repo = image["RepoDigests"][0].split("@")[0].removeprefix("ghcr.io/")
    runs = subprocess.run(
        ["gh", "run", "list", "-R", repo, "-w", "image", "-L", "30", "--json", "headSha,displayTitle,createdAt,updatedAt"],
        capture_output=True,
        text=True,
    )
    if runs.returncode != 0:
        return "commit unknown (gh run list failed)"
    for run in json.loads(runs.stdout):
        if parse(run["createdAt"]) <= parse(built) <= parse(run["updatedAt"]):
            return f"{repo}@{run['headSha'][:7]} {run['displayTitle']!r}"
    return f"commit unknown (no {repo} image build at that time)"


def parse(timestamp: str) -> datetime:
    # Docker gives nanoseconds, which fromisoformat does not take.
    return datetime.fromisoformat(timestamp.rstrip("Z").split(".")[0]).replace(tzinfo=timezone.utc)


def ago(timestamp: str) -> str:
    minutes = int((datetime.now(timezone.utc) - parse(timestamp)).total_seconds() // 60)
    days, hours, minutes = minutes // 1440, minutes // 60 % 24, minutes % 60
    return " ".join(f"{n}{unit}" for n, unit in [(days, "d"), (hours, "h"), (minutes, "m")] if n) or "under a minute"
