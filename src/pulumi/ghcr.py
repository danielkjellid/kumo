from box import run
from settings import config

# Lets deploy.sh pull the private app images.
run(
    "ghcr-login",
    f"docker login ghcr.io -u {config.require('ghcrUser')} --password-stdin",
    config.require_secret("ghcrToken"),
)
