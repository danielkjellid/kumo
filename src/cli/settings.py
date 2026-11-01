import base64
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass


def cookie_secret() -> str:
    # oauth2-proxy wants 32 random bytes as URL-safe base64.
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


@dataclass(frozen=True)
class Setting:
    key: str
    prompt: str
    secret: bool = False
    default: str | None = None
    generate: Callable[[], str] | None = None


# What `kumo init` asks for, in this order. The secret ones are `kumo secret`'s.
SETTINGS = {
    "hetzner-token": Setting("hcloud:token", "Hetzner API token (read and write)", secret=True),
    "server-type": Setting("serverType", "Server type", default="cpx12"),
    "location": Setting("location", "Hetzner location", default="hel1"),
    "domain": Setting("domain", "Domain, without https://"),
    "bucket": Setting("bucket", "Object Storage bucket name"),
    "s3-access-key": Setting("s3AccessKey", "Object Storage access key", secret=True),
    "s3-secret-key": Setting("s3SecretKey", "Object Storage secret key", secret=True),
    "ghcr-user": Setting("ghcrUser", "GitHub user that owns the app images"),
    "ghcr-token": Setting("ghcrToken", "GitHub classic token with read:packages", secret=True),
    "google-client-id": Setting("env.auth.GOOGLE_CLIENT_ID", "Google OAuth client ID"),
    "google-client-secret": Setting("env.auth.GOOGLE_CLIENT_SECRET", "Google OAuth client secret", secret=True),
    "microsoft-client-id": Setting("env.auth.MICROSOFT_CLIENT_ID", "Microsoft app (client) ID"),
    "microsoft-client-secret": Setting(
        "env.auth.MICROSOFT_CLIENT_SECRET", "Microsoft client secret value", secret=True
    ),
    "dex-client-secret": Setting(
        "env.auth.OAUTH2_PROXY_CLIENT_SECRET",
        "Secret between oauth2-proxy and Dex",
        secret=True,
        generate=lambda: secrets.token_hex(32),
    ),
    "cookie-secret": Setting(
        "env.auth.OAUTH2_PROXY_COOKIE_SECRET", "Session cookie secret", secret=True, generate=cookie_secret
    ),
}
SECRET_NAMES = [name for name, setting in SETTINGS.items() if setting.secret]
