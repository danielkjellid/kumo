import pulumi

from box import write_file
from settings import config

# Who may open which app. Signing in at all takes a place on at least one list;
# caddy.py narrows it per app.
# The lists are encrypted in Pulumi.prod.yaml to keep emails out of the public
# repo. The files on the box and Pulumi's state may hold them in the clear, and
# that keeps `kumo commit` previews readable.
access: pulumi.Output[dict[str, list[str]]] = pulumi.Output.unsecret(config.require_secret_object("access"))
# oauth2-proxy runs as a user that cannot read env/.
write_file(
    "allowed-emails",
    "/srv/infra/allowed-emails",
    access.apply(lambda lists: "".join(f"{email}\n" for email in sorted({e for emails in lists.values() for e in emails}))),
    private=False,
)
