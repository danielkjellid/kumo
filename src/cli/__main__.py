"""kumo: set up the stack and run the box without typing Pulumi config paths."""

import click
from pulumi import automation as auto

from .box import deploy, logs, ssh, status
from .commit import commit
from .env import env
from .init import init
from .provision import provision
from .secret import secret


@click.group()
@click.option("--stack", default="prod", envvar="KUMO_STACK", show_default=True, help="Pulumi stack to use.")
@click.pass_context
def cli(ctx: click.Context, stack: str) -> None:
    """Set up and run the kumo box."""
    ctx.obj = stack


for command in [init, commit, provision, env, secret, deploy, ssh, status, logs]:
    cli.add_command(command)


def main() -> None:
    try:
        cli(prog_name="kumo")
    except auto.errors.CommandError:
        # Pulumi has already printed why, through on_output and on_error.
        raise SystemExit(1)


if __name__ == "__main__":
    main()
