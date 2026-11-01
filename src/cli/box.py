import os

import click

from .stack import open_stack


def on_box(stack_name: str, command: str | None = None) -> None:
    ip = open_stack(stack_name).outputs()["ipv4"].value
    # Trust the box's host key on first contact, without a prompt that needs a
    # terminal, and still refuse if it changes later.
    ssh = ["ssh", "-t", "-o", "StrictHostKeyChecking=accept-new", f"deploy@{ip}"]
    os.execvp("ssh", ssh + ([f"cd /srv/infra && {command}"] if command else []))


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
