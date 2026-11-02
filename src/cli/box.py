import os

import click

from .apps import APPS
from .stack import open_stack


def ssh_args(stack_name: str, *options: str) -> list[str]:
    ip = open_stack(stack_name).outputs()["ipv4"].value
    # Trust the box's host key on first contact, without a prompt that needs a
    # terminal, and still refuse if it changes later.
    return ["ssh", *options, "-o", "StrictHostKeyChecking=accept-new", f"deploy@{ip}"]


def on_box(stack_name: str, command: str | None = None) -> None:
    os.execvp("ssh", ssh_args(stack_name, "-t") + ([f"cd /srv/infra && {command}"] if command else []))


@click.command()
@click.pass_obj
def ssh(stack_name: str) -> None:
    """Open a shell on the box as deploy."""
    on_box(stack_name)


@click.command()
@click.pass_obj
def status(stack_name: str) -> None:
    """Show the containers running on the box."""
    on_box(stack_name, "docker compose ps")


@click.command()
@click.argument("service", required=False)
@click.option("-f", "--follow", is_flag=True, help="Keep printing new lines.")
@click.pass_obj
def logs(stack_name: str, service: str | None, follow: bool) -> None:
    """Show the last 200 log lines, of one service or all of them."""
    on_box(stack_name, f"docker compose logs --tail 200 {'-f ' if follow else ''}{service or ''}")


@click.command()
@click.argument("app", type=click.Choice(APPS), required=False)
@click.pass_obj
def deploy(stack_name: str, app: str | None) -> None:
    """Pull new images and restart what changed, without waiting for cron.

    With an app, only that one. If cron is already deploying, this waits for it.
    """
    if app is None:
        return on_box(stack_name, "bin/deploy.sh")
    # Same lock as deploy.sh, so this never races a cron run.
    on_box(stack_name, f"flock -w 600 bin/deploy.sh sh -c 'docker compose pull {app} && docker compose up -d {app}'")
