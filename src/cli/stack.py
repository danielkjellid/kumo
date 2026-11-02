import json
from pathlib import Path

import click
from pulumi import automation as auto

# The repo root, where Pulumi.yaml and the stack files live.
ROOT = Path(__file__).resolve().parents[2]
# Config keys holding lists or maps. Every other key is a plain string.
OBJECT_KEYS = {"authorizedKeys", "access", "env"}


class Config:
    """The stack's config as nested values. Writes are staged until save()."""

    def __init__(self, stack: auto.Stack):
        self.stack = stack
        self.values: dict = {}
        self.staged: dict[str, auto.ConfigValue] = {}
        for key, value in stack.get_all_config().items():
            name = key.removeprefix("kumo:")
            self.values[name] = json.loads(value.value) if name in OBJECT_KEYS else value.value

    def get(self, path: str):
        if path in self.staged:
            return self.staged[path].value
        node = self.values
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        # `config set --path` stores "0" or "true" as a number or bool. Hand them
        # back as the strings they were set as.
        return node if node is None or isinstance(node, (str, dict, list)) else json.dumps(node)

    def set(self, path: str, value: str, secret: bool = False) -> None:
        if value != self.get(path):
            self.staged[path] = auto.ConfigValue(value=value, secret=secret)

    def remove(self, path: str) -> None:
        if self.get(path) is not None:
            self.stack.remove_config(path, path=True)

    def set_list(self, path: str, items: list[str], secret: bool = False) -> None:
        # Pulumi sets lists one index at a time, so clear the old one first.
        self.remove(path)
        for i, item in enumerate(items):
            self.staged[f"{path}[{i}]"] = auto.ConfigValue(value=item, secret=secret)

    def save(self) -> None:
        if self.staged:
            self.stack.set_all_config(self.staged, path=True)
        click.echo("Saved. Run `kumo commit` to put it on the box.")


def open_stack(name: str, create: bool = False) -> auto.Stack:
    try:
        select = auto.create_or_select_stack if create else auto.select_stack
        return select(stack_name=name, work_dir=str(ROOT))
    except auto.StackNotFoundError:
        raise click.ClickException(f"No stack named {name}. Run `kumo init` first.")


def load(name: str) -> Config:
    return Config(open_stack(name))
