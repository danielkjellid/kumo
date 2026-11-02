import secrets
import subprocess
from pathlib import Path

import click

from .apps import APPS
from .provision import emails
from .settings import SETTINGS, Setting
from .stack import Config, open_stack


@click.command()
@click.option("--skip-set", is_flag=True, help="Only ask for settings that are not set yet.")
@click.pass_obj
def init(stack_name: str, skip_set: bool) -> None:
    """Ask for every setting the box needs, one by one.

    Safe to rerun: Enter keeps what is set, and secrets stay unless you say so.
    Enter on an empty prompt leaves that setting for later.
    """
    config = Config(open_stack(stack_name, create=True))

    # Changing these later replaces the server, so they are only asked for once.
    if config.get("authorizedKeys") is None:
        laptop = public_key("Your laptop's public key", "~/.ssh/id_ed25519.pub")
        deploy = public_key("The GitHub Actions deploy key", "~/.ssh/infra-deploy.pub", generate=True)
        config.set_list("authorizedKeys", [laptop, deploy])

    for setting in SETTINGS.values():
        current = config.get(setting.key)
        if skip_set and current is not None:
            continue
        value = ask(setting, current)
        if value:
            config.set(setting.key, value, secret=setting.secret)

    for app in APPS:
        if config.get(f"env.{app}.SECRET_KEY") is None:
            config.set(f"env.{app}.SECRET_KEY", secrets.token_urlsafe(50), secret=True)
            click.echo(f"Generated a SECRET_KEY for {app}.")

    if not config.get("access"):
        answer = click.prompt("Emails with access to every app, comma separated")
        everyone = emails(tuple(email.strip() for email in answer.split(",")))
        for app in APPS:
            config.set_list(f"access.{app}", everyone, secret=True)

    config.save()
    if left := missing(config):
        click.echo(f"Still to set: {', '.join(left)}. Run `kumo init --skip-set` when you have them.")


def missing(config: Config) -> list[str]:
    return [name for name, setting in SETTINGS.items() if config.get(setting.key) is None]


def ask(setting: Setting, current: str | None) -> str:
    if current is not None and setting.secret:
        if not click.confirm(f"{setting.prompt} is set. Replace it?", default=False):
            return current
    elif current is not None:
        return prompt(setting.prompt, default=current)
    if setting.generate:
        click.echo(f"{setting.prompt}: generated.")
        return setting.generate()
    # An empty answer comes back as "", which init leaves unset.
    return prompt(setting.prompt, default=setting.default or "", show_default=bool(setting.default), hide_input=setting.secret)


def prompt(text: str, **kwargs) -> str:
    # Values pasted from a console often come wrapped in quotes.
    value = click.prompt(text, type=str, **kwargs).strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def public_key(prompt: str, default: str, generate: bool = False) -> str:
    path = Path(click.prompt(prompt, default=default)).expanduser()
    if not path.exists() and generate and click.confirm(f"{path} does not exist. Create it?", default=True):
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(path.with_suffix("")), "-N", "", "-C", "github-deploy"],
            check=True,
        )
    if not path.exists():
        raise click.ClickException(f"{path} does not exist.")
    return path.read_text().strip()
