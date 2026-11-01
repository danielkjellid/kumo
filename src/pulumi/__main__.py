# One module per part of the box. Importing one declares its resources.
import pulumi

import access  # noqa: F401
import caddy  # noqa: F401
import dex  # noqa: F401
import env  # noqa: F401
import ghcr  # noqa: F401
import s3  # noqa: F401
from server import server

pulumi.export("ipv4", server.ipv4_address)
