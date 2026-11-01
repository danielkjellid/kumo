import pulumi

import s3
from box import render, write_file
from cli.apps import APPS
from settings import config, location

write_file("env-root", "/srv/infra/.env", f"DOMAIN={config.require('domain')}\n")

app_env = config.require_secret_object("env")
# auth.env is shared by the dex and auth services.
for app in ["auth", *APPS]:
    write_file(f"env-{app}", f"/srv/infra/env/{app}.env", app_env.apply(lambda env, app=app: render(env[app])))

write_file(
    "env-litestream",
    "/srv/infra/env/litestream.env",
    pulumi.Output.all(s3.access_key, s3.secret_key).apply(
        lambda keys: render(
            {
                "LITESTREAM_BUCKET": config.require("bucket"),
                "LITESTREAM_ENDPOINT": s3.endpoint,
                "LITESTREAM_REGION": location,
                "LITESTREAM_ACCESS_KEY_ID": keys[0],
                "LITESTREAM_SECRET_ACCESS_KEY": keys[1],
            }
        )
    ),
)
