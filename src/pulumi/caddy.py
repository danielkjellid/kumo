from urllib.parse import quote

from access import access
from box import if_running, write_file
from cli.apps import APPS

# The sign-in snippet and the auth site. site() adds one block per app below.
BASE = """\
(login) {
	forward_auth auth:4180 {
		uri /oauth2/auth?allowed_emails={args[0]}
		header_up X-Real-IP {remote_host}
		@login status 401
		handle_response @login {
			redir * https://auth.{$DOMAIN}/oauth2/start?rd={scheme}://{host}{uri}
		}
		@denied status 403
		handle_response @denied {
			respond "You don't have access to this app." 403
		}
	}
}

auth.{$DOMAIN} {
	handle /dex/* {
		reverse_proxy dex:5556
	}
	handle {
		reverse_proxy auth:4180 {
			header_up X-Real-IP {remote_host}
		}
	}
}
"""


def site(app: str) -> str:
    # oauth2-proxy reads an empty list as "anyone signed in", so an app nobody
    # was given gets a list that matches no one.
    emails = ",".join(quote(email, safe="@") for email in access.get(app, [])) or "nobody"
    return f"\n{app}.{{$DOMAIN}} {{\n\timport login {emails}\n\treverse_proxy {app}:8000\n}}\n"


write_file(
    "caddyfile",
    "/srv/infra/Caddyfile",
    BASE + "".join(site(app) for app in APPS),
    private=False,
    then=if_running("caddy", "exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile"),
)
