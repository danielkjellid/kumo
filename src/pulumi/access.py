from box import write_file
from settings import config

# Who may open which app. Signing in at all takes a place on at least one list;
# caddy.py narrows it per app.
access: dict[str, list[str]] = config.require_object("access")
everyone = sorted({email for emails in access.values() for email in emails})
# Not secret, and oauth2-proxy runs as a user that cannot read env/.
write_file("allowed-emails", "/srv/infra/allowed-emails", "".join(f"{email}\n" for email in everyone), private=False)
