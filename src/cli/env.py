import re

import click

from .apps import APPS
from .stack import load


@click.group()
def env() -> None:
    """Environment variables for each app, written to env/<app>.env on the box."""


@env.command("list")
@click.argument("app", type=click.Choice(APPS), required=False)
@click.option("--show", is_flag=True, help="Show the values.")
@click.pass_obj
def env_list(stack_name: str, app: str | None, show: bool) -> None:
    """List each app's variables, hiding the values unless --show."""
    config = load(stack_name)
    for name in [app] if app else APPS:
        click.echo(f"{name}:")
        for key, value in sorted((config.get(f"env.{name}") or {}).items()):
            click.echo(f"  {key}={value if show else '********'}")


@env.command("set")
@click.argument("app", type=click.Choice(APPS))
@click.argument("key")
@click.argument("value", required=False)
@click.option("--plain", is_flag=True, help="Store unencrypted, for values that are not secret.")
@click.pass_obj
def env_set(stack_name: str, app: str, key: str, value: str | None, plain: bool) -> None:
    """Set KEY for APP. Leave out VALUE to type it hidden."""
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
        raise click.BadParameter("Use upper case, digits and underscores.", param_hint="KEY")
    if value is None:
        value = click.prompt(key, hide_input=not plain)
    config = load(stack_name)
    config.set(f"env.{app}.{key}", value, secret=not plain)
    config.save()


@env.command("unset")
@click.argument("app", type=click.Choice(APPS))
@click.argument("key")
@click.pass_obj
def env_unset(stack_name: str, app: str, key: str) -> None:
    """Remove KEY from APP."""
    config = load(stack_name)
    if config.get(f"env.{app}.{key}") is None:
        raise click.ClickException(f"{app} has no {key}.")
    config.remove(f"env.{app}.{key}")
    config.save()
