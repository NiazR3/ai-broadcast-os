"""Poll engine — create, vote, close, and tally polls."""

from __future__ import annotations

import logging
import uuid
from time import time
from typing import Optional

from broadcast.audience.models import Poll, PollOption, PollStatus, PollVote

logger = logging.getLogger(__name__)


class PollEngine:
    """In-memory poll engine supporting create, vote, close, and tally."""

    def __init__(self) -> None:
        self._polls: dict[str, Poll] = {}
        self._votes: dict[str, dict[str, PollVote]] = {}  # poll_id -> {user_id: vote}

    def create_poll(self, question: str, options: list[str], duration_seconds: int = 60) -> Poll:
        """Create a new poll and activate it immediately."""
        poll = Poll.model_construct(
            id=uuid.uuid4().hex[:12],
            question=question,
            options=[PollOption(text=opt) for opt in options],
            status=PollStatus.ACTIVE,
            duration_seconds=max(0, duration_seconds),
            created_at=time(),
        )
        self._polls[poll.id] = poll
        self._votes[poll.id] = {}
        logger.info("Poll created: '%s' (%s)", question, poll.id)
        return poll

    def vote(self, poll_id: str, option_index: int, user_id: str) -> PollVote:
        """Cast a vote. Raises ValueError if poll not found, closed, already voted, or invalid option."""
        poll = self._polls.get(poll_id)
        if poll is None:
            raise ValueError(f"Poll '{poll_id}' not found")
        if poll.status == PollStatus.CLOSED:
            raise ValueError(f"Poll '{poll_id}' is closed")
        if poll.status == PollStatus.PENDING:
            raise ValueError(f"Poll '{poll_id}' is not active")

        # Auto-close if expired
        elapsed = time() - poll.created_at
        if elapsed >= poll.duration_seconds:
            self.close_poll(poll_id)
            raise ValueError(f"Poll '{poll_id}' has expired and is closed")

        if option_index < 0 or option_index >= len(poll.options):
            raise ValueError(f"Invalid option index {option_index}")

        user_votes = self._votes[poll_id]
        if user_id in user_votes:
            raise ValueError(f"User '{user_id}' already voted on poll '{poll_id}'")

        vote = PollVote(poll_id=poll_id, option_index=option_index, user_id=user_id, timestamp=time())
        user_votes[user_id] = vote
        poll.options[option_index].votes += 1
        logger.debug("Vote cast: user '%s' -> option %d on poll '%s'", user_id, option_index, poll_id)
        return vote

    def close_poll(self, poll_id: str) -> Poll:
        """Force-close a poll. Raises ValueError if not found."""
        poll = self._polls.get(poll_id)
        if poll is None:
            raise ValueError(f"Poll '{poll_id}' not found")
        poll.status = PollStatus.CLOSED
        poll.closed_at = time()
        logger.info("Poll closed: '%s'", poll_id)
        return poll

    def get_poll(self, poll_id: str) -> Optional[Poll]:
        """Get a poll by ID."""
        return self._polls.get(poll_id)

    def get_active_poll(self) -> Optional[Poll]:
        """Get the currently active poll (if any).

        If duration has expired, auto-closes the poll and returns None.
        """
        for poll in self._polls.values():
            if poll.status == PollStatus.ACTIVE:
                elapsed = time() - poll.created_at
                if elapsed >= poll.duration_seconds:
                    self.close_poll(poll.id)
                    continue
                return poll
        return None

    def list_polls(self, include_closed: bool = False) -> list[Poll]:
        """List all polls, optionally including closed ones."""
        if include_closed:
            return list(self._polls.values())
        return [p for p in self._polls.values() if p.status != PollStatus.CLOSED]

    def get_results(self, poll_id: str) -> dict:
        """Get poll results with vote counts and winner."""
        poll = self._polls.get(poll_id)
        if poll is None:
            raise ValueError(f"Poll '{poll_id}' not found")
        total = sum(o.votes for o in poll.options)
        winner = max(poll.options, key=lambda o: o.votes) if poll.options else None
        return {
            "poll_id": poll_id,
            "question": poll.question,
            "status": poll.status.value,
            "total_votes": total,
            "options": [{"text": o.text, "votes": o.votes} for o in poll.options],
            "winner": winner.text if winner else None,
            "winner_votes": winner.votes if winner else 0,
        }
