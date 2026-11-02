import pulumi
import pulumi_command as command

from server import server

# Files on the box are written over SSH as deploy, through your SSH agent.
# Editing them on the box is undone by the next `pulumi up`.
connection = command.remote.ConnectionArgs(host=server.ipv4_address, user="deploy")

# Docker and /srv/infra come from cloud-init, so wait for first boot to finish.
first_boot = command.remote.Command(
    "first-boot",
    connection=connection,
    create="sudo cloud-init status --wait >/dev/null",
)


def run(name: str, create: str, stdin: pulumi.Input[str]) -> command.remote.Command:
    return command.remote.Command(
        name,
        connection=connection,
        create=create,
        stdin=stdin,
        opts=pulumi.ResourceOptions(depends_on=[first_boot]),
    )


def write_file(
    name: str, path: str, content: pulumi.Input[str], private: bool = True, then: str = ""
) -> command.remote.Command:
    """Write content to path on the box, then run `then` there, if given."""
    umask = "077" if private else "022"
    return run(name, f"umask {umask} && mkdir -p $(dirname {path}) && cat > {path}{' && ' + then if then else ''}", content)


def if_running(service: str, command: str) -> str:
    """A shell line that runs a compose command only once the service is up."""
    return (
        f"cd /srv/infra && if [ -n \"$(docker compose ps -q --status running {service} 2>/dev/null)\" ];"
        f" then docker compose {command}; fi"
    )


def render(values: dict[str, str]) -> str:
    # Compose expands $VAR inside env_file values; $$ is a literal $.
    return "".join(f"{key}={str(value).replace('$', '$$')}\n" for key, value in values.items())
