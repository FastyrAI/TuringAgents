"""
Programmatically create a vhost, user, and permissions in RabbitMQ via the Management API.

Required env (can be mounted via k8s Secret):
  RABBITMQ_MGMT_URL, RABBITMQ_ADMIN_USER, RABBITMQ_ADMIN_PASS,
  RABBITMQ_SETUP_VHOST, RABBITMQ_SETUP_USER, RABBITMQ_SETUP_PASS,
  RABBITMQ_PERMISSIONS_CONFIGURE, RABBITMQ_PERMISSIONS_WRITE, RABBITMQ_PERMISSIONS_READ
"""

import os
import sys
import json
import base64
import httpx


def _auth_header(user: str, pw: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def main() -> None:
    mgmt = os.getenv("RABBITMQ_MGMT_URL", "http://localhost:15672").rstrip("/")
    admin_user = os.getenv("RABBITMQ_ADMIN_USER", "guest")
    admin_pass = os.getenv("RABBITMQ_ADMIN_PASS", "guest")

    vhost = os.getenv("RABBITMQ_SETUP_VHOST", "/prod")
    app_user = os.getenv("RABBITMQ_SETUP_USER", "app-user")
    app_pass = os.getenv("RABBITMQ_SETUP_PASS", "change-me")

    perm_cfg = os.getenv("RABBITMQ_PERMISSIONS_CONFIGURE", ".*")
    perm_write = os.getenv("RABBITMQ_PERMISSIONS_WRITE", ".*")
    perm_read = os.getenv("RABBITMQ_PERMISSIONS_READ", ".*")

    headers = _auth_header(admin_user, admin_pass)
    vhost_enc = vhost if vhost != "/" else "%2F"

    with httpx.Client(timeout=10.0) as client:
        # Create vhost
        r = client.put(f"{mgmt}/api/vhosts/{vhost_enc}", headers=headers)
        if r.status_code not in (201, 204):
            print(f"vhost create: {r.status_code} {r.text}")
        # Create user
        r = client.put(
            f"{mgmt}/api/users/{app_user}", headers=headers, json={"password": app_pass, "tags": ""}
        )
        if r.status_code not in (201, 204):
            print(f"user create: {r.status_code} {r.text}")
        # Set permissions
        r = client.put(
            f"{mgmt}/api/permissions/{vhost_enc}/{app_user}",
            headers=headers,
            json={"configure": perm_cfg, "write": perm_write, "read": perm_read},
        )
        if r.status_code not in (201, 204):
            print(f"permissions: {r.status_code} {r.text}")

    # Output the connection URL
    amqps_host = os.getenv("RABBITMQ_AMQPS_HOST", "rabbitmq")
    amqps_port = os.getenv("RABBITMQ_AMQPS_PORT", "5671")
    vhost_url = vhost if vhost != "/" else "%2F"
    print(
        json.dumps(
            {
                "amqps_url": f"amqps://{app_user}:{app_pass}@{amqps_host}:{amqps_port}/{vhost_url}",
                "note": "Use this URL in RABBITMQ_URL to connect over TLS",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()


