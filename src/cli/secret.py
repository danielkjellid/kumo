import click

from .init import prompt
from .settings import SECRET_NAMES, SETTINGS
from .stack import load


@click.group()
def secret() -> None:
    """Tokens and keys for Hetzner, GitHub, Google, Microsoft and the sign-in."""


@secret.command("list")
@click.pass_obj
def secret_list(stack_name: str) -> None:
    """Show which secrets are set, without their values."""
    config = load(stack_name)
    for name in SECRET_NAMES:
        setting = SETTINGS[name]
        state = "set" if config.get(setting.key) is not None else "missing"
        click.echo(f"{name:<26} {state}{'  (generated)' if setting.generate else ''}")


@secret.command("set")
@click.argument("name", type=click.Choice(SECRET_NAMES))
@click.pass_obj
def secret_set(stack_name: str, name: str) -> None:
    """Replace a secret. Generated ones get a new random value.

    The others are asked for at a hidden prompt, not given as an argument, so
    they stay out of your shell history.
    """
    setting = SETTINGS[name]
    config = load(stack_name)
    value = setting.generate() if setting.generate else prompt(setting.prompt, hide_input=True)
    config.set(setting.key, value, secret=True)
    config.save()
