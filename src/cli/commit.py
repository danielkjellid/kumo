import click
from pulumi import automation as auto

from .init import missing
from .stack import Config, open_stack


@click.command()
@click.option("--yes", is_flag=True, help="Apply without asking.")
@click.pass_obj
def commit(stack_name: str, yes: bool) -> None:
    """Show what would change, then apply it if you agree."""
    stack = open_stack(stack_name)
    if left := missing(Config(stack)):
        raise click.ClickException(f"Not set yet: {', '.join(left)}. Run `kumo init --skip-set` first.")
    preview = stack.preview(diff=True, color="always", on_output=click.echo, on_error=echo_error)
    if all(op == auto.OpType.SAME or count == 0 for op, count in preview.change_summary.items()):
        click.echo("Nothing to change.")
        return
    if yes or click.confirm("Apply these changes?", default=False):
        stack.up(color="always", on_output=click.echo, on_error=echo_error)


def echo_error(line: str) -> None:
    click.echo(line, err=True)
