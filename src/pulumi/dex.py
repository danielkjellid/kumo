import hashlib
import json
from pathlib import Path

import pulumi
import pulumi_command as command

from box import connection, if_running, write_file
from settings import config

domain = config.require("domain")


def connector(kind: str, name: str, env: str) -> dict:
    # Dex expands $VARS in connector config, so the secrets stay in auth.env.
    return {
        "type": kind,
        "id": kind,
        "name": name,
        "config": {
            "clientID": f"${env}_CLIENT_ID",
            "clientSecret": f"${env}_CLIENT_SECRET",
            "redirectURI": f"https://auth.{domain}/dex/callback",
        },
    }


# The sign-in page in front of oauth2-proxy. JSON is valid YAML to Dex.
dex = {
    "issuer": f"https://auth.{domain}/dex",
    "storage": {"type": "memory"},
    "web": {"http": "0.0.0.0:5556"},
    "frontend": {
        "issuer": "kumo",
        "dir": "/srv/dex/web",
        "theme": "kumo",
        "logoURL": "theme/logo.svg",
        "extra": {"host": f"auth.{domain}"},
    },
    "oauth2": {"skipApprovalScreen": True},
    "staticClients": [
        {
            "id": "oauth2-proxy",
            "name": "kumo",
            "secretEnv": "OAUTH2_PROXY_CLIENT_SECRET",
            "redirectURIs": [f"https://auth.{domain}/oauth2/callback"],
        }
    ],
    "connectors": [
        connector("google", "Google", "GOOGLE"),
        # Work, school and personal accounts. Dex uses the userPrincipalName as
        # the email, which Microsoft only allows in domains the tenant verified.
        connector("microsoft", "Microsoft", "MICROSOFT"),
    ],
}
write_file(
    "dex-config",
    "/srv/infra/dex.json",
    json.dumps(dex, indent=2) + "\n",
    private=False,
    then=if_running("dex", "restart dex"),
)

# The sign-in pages, in Dex's web dir layout. Dex reads them at start, so any
# change restarts it once, after every file is written.
WEB = Path(__file__).parent / "dex-web"
# Skips dotfiles like .DS_Store.
pages = sorted(path.relative_to(WEB) for path in WEB.rglob("[!.]*") if path.is_file())
written = [
    write_file(f"dex-web-{page}", f"/srv/infra/dex-web/{page}", (WEB / page).read_text(), private=False)
    for page in pages
]
command.remote.Command(
    "dex-web-restart",
    connection=connection,
    create=if_running("dex", "restart dex"),
    triggers=[hashlib.sha256(b"".join((WEB / page).read_bytes() for page in pages)).hexdigest()],
    opts=pulumi.ResourceOptions(depends_on=written),
)
