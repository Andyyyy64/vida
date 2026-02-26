"""Notification delivery — Discord webhook and LINE Notify support."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from life.config import NotifyConfig

log = logging.getLogger(__name__)


def send_notification(config: NotifyConfig, title: str, body: str) -> bool:
    """Send a notification via configured provider. Returns True on success."""
    if not config.enabled or not config.webhook_url:
        return False

    if config.provider == "discord":
        return _send_discord(config.webhook_url, title, body)
    elif config.provider == "line":
        return _send_line(config.webhook_url, title, body)
    else:
        log.warning("Unknown notification provider: %s", config.provider)
        return False


def _send_discord(webhook_url: str, title: str, body: str) -> bool:
    """Send message via Discord webhook."""
    # Discord embeds have 4096 char limit for description
    content = body[:4000] if len(body) > 4000 else body

    payload = {
        "embeds": [{
            "title": title,
            "description": content,
            "color": 0x7C3AED,  # purple
        }]
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 204):
                log.info("Discord notification sent: %s", title)
                return True
            else:
                log.warning("Discord webhook returned %d", resp.status)
                return False
    except urllib.error.URLError as e:
        log.error("Discord notification failed: %s", e)
        return False
    except Exception as e:
        log.error("Discord notification error: %s", e)
        return False


def _send_line(webhook_url: str, title: str, body: str) -> bool:
    """Send message via LINE Notify.

    webhook_url should be the LINE Notify access token.
    The actual endpoint is fixed: https://notify-api.line.me/api/notify
    """
    # LINE Notify has 1000 char limit
    message = f"\n{title}\n\n{body}"
    if len(message) > 1000:
        message = message[:997] + "..."

    try:
        data = urllib.parse.urlencode({"message": message}).encode("utf-8")
        req = urllib.request.Request(
            "https://notify-api.line.me/api/notify",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {webhook_url}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                log.info("LINE notification sent: %s", title)
                return True
            else:
                log.warning("LINE Notify returned %d", resp.status)
                return False
    except urllib.error.URLError as e:
        log.error("LINE notification failed: %s", e)
        return False
    except Exception as e:
        log.error("LINE notification error: %s", e)
        return False
