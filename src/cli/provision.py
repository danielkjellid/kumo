import click

from .apps import APPS
from .stack import load


def emails(values: tuple[str, ...]) -> list[str]:
    for value in values:
        if "@" not in value:
            raise click.BadParameter(f"{value} is not an email address.")
    return list(values)


@click.group()
def provision() -> None:
    """Who may open which app, by the email of their Google or Microsoft account."""


@provision.command("list")
@click.argument("app", type=click.Choice(APPS), required=False)
@click.pass_obj
def provision_list(stack_name: str, app: str | None) -> None:
    """List who may open each app."""
    config = load(stack_name)
    for name in [app] if app else APPS:
        click.echo(f"{name}:")
        for email in config.get(f"access.{name}") or ["(nobody)"]:
            click.echo(f"  {email}")


@provision.command("add")
@click.argument("app", type=click.Choice(APPS))
@click.argument("email", nargs=-1, required=True)
@click.pass_obj
def provision_add(stack_name: str, app: str, email: tuple[str, ...]) -> None:
    """Give EMAIL access to APP."""
    config = load(stack_name)
    current = config.get(f"access.{app}") or []
    # Encrypted, so the emails stay out of the public repo.
    config.set_list(f"access.{app}", current + [e for e in emails(email) if e not in current], secret=True)
    config.save()


@provision.command("remove")
@click.argument("app", type=click.Choice(APPS))
@click.argument("email", nargs=-1, required=True)
@click.pass_obj
def provision_remove(stack_name: str, app: str, email: tuple[str, ...]) -> None:
    """Take APP away from EMAIL."""
    config = load(stack_name)
    current = config.get(f"access.{app}") or []
    missing = [e for e in email if e not in current]
    if missing:
        raise click.ClickException(f"Not on {app}'s list: {', '.join(missing)}")
    config.set_list(f"access.{app}", [e for e in current if e not in email], secret=True)
    config.save()
