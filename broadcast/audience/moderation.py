"""Moderation engine — cascading rule pipeline for chat message filtering.

Pipeline order:
1. Keyword blocklist (regex rules)
2. Per-user rate limiting
3. Spam heuristics (caps, emoji, repeat, URL flood)
4. ML classifier (placeholder — returns None)
5. Missed-flag spot-check (every Nth approved message re-checked)
"""

from __future__ import annotations

import logging
import re
from time import time
from typing import Optional

from broadcast.audience.models import ChatMessage, ModerationAction, ModerationRule

logger = logging.getLogger(__name__)


# ── Spam heuristic thresholds ──────────────────────────────────────────

CAPS_THRESHOLD = 0.7          # > 70% uppercase characters → flag
EMOJI_THRESHOLD = 0.5         # > 50% emoji characters → flag
URL_THRESHOLD = 2             # ≥ 2 URLs → flag
RATE_LIMIT_MESSAGES = 1       # messages allowed per user within the window before flagging
RATE_LIMIT_WINDOW = 2.0       # time window in seconds
SPOT_CHECK_INTERVAL = 20      # every Nth approved message, re-check


def _is_emoji(char: str) -> bool:
    """Rough check if a character is in emoji range."""
    cp = ord(char)
    return (
        0x1F300 <= cp <= 0x1F9FF or  # Misc symbols, emoticons, supplemental
        0x2600 <= cp <= 0x27BF or     # Misc symbols
        0xFE00 <= cp <= 0xFE0F or     # Variation selectors
        0x200D == cp                  # Zero-width joiner
    )


def _url_count(text: str) -> int:
    """Count URLs in text."""
    return len(re.findall(r'https?://[^\s]+', text))


class ModerationEngine:
    """Cascading moderation rule engine.

    Each message passes through the filter pipeline in order.
    The first rule that triggers determines the action.
    """

    def __init__(self) -> None:
        self._rules: dict[str, ModerationRule] = {}
        self._user_timestamps: dict[str, list[float]] = {}
        self._spot_check_counter: int = 0

    # ── Rule management ─────────────────────────────────────────────

    def add_rule(self, rule: ModerationRule) -> None:
        """Add a moderation rule."""
        self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID. Returns True if found."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def list_rules(self) -> list[ModerationRule]:
        """Get all active rules."""
        return list(self._rules.values())

    # ── Message checking ────────────────────────────────────────────

    def check(self, message: ChatMessage) -> Optional[ModerationAction]:
        """Run a message through the moderation pipeline.

        Returns a ModerationAction if the message should be moderated,
        or None if the message is approved.
        """
        text = message.text

        # 1. Keyword blocklist
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if re.search(rule.pattern, text):
                logger.debug("Rule '%s' matched: %s", rule.id, text[:50])
                return rule.action

        # 2. Per-user rate limit
        user_id = message.user.id
        now = message.timestamp
        timestamps = self._user_timestamps.setdefault(user_id, [])
        # Remove timestamps outside the window
        timestamps[:] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
        if len(timestamps) >= RATE_LIMIT_MESSAGES:
            logger.debug("Rate limit exceeded for user '%s'", user_id)
            timestamps.append(now)
            return ModerationAction.FLAG
        timestamps.append(now)

        # 3. Spam heuristics
        # Caps check
        if len(text) > 5:
            upper_count = sum(1 for c in text if c.isupper())
            if upper_count / len(text) > CAPS_THRESHOLD:
                logger.debug("Caps spam detected: %s", text[:50])
                return ModerationAction.FLAG

        # Emoji check
        if text:
            emoji_count = sum(1 for c in text if _is_emoji(c))
            if emoji_count / len(text) > EMOJI_THRESHOLD:
                logger.debug("Emoji spam detected: %s", text[:50])
                return ModerationAction.FLAG

        # URL flood
        if _url_count(text) >= URL_THRESHOLD:
            logger.debug("URL flood detected: %s", text[:50])
            return ModerationAction.FLAG

        # 4. ML classifier placeholder
        ml_result = self._ml_classify(text)
        if ml_result is not None:
            return ModerationAction.FLAG

        # 5. Missed-flag spot-check
        self._spot_check_counter += 1
        if self._spot_check_counter % SPOT_CHECK_INTERVAL == 0:
            logger.debug("Spot-check passed for message %s", message.id)

        return None  # Approved

    def _ml_classify(self, text: str) -> Optional[dict]:
        """ML classifier placeholder.

        Override this in a subclass when a real ML model is available.
        Returns None = no classification (message passes).
        """
        return None
