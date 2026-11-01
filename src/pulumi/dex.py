import json

from box import if_running, write_file
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
    "frontend": {"issuer": "kumo"},
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
