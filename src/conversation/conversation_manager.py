"""Conversation history and follow-up context management."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


FOLLOW_UP_HINTS = re.compile(
    r"\b(same|also|that|those|previous|above|instead|for the|now show|compare|"
    r"what about|how about|filter|only|break(ing)? down)\b",
    re.IGNORECASE,
)

AMBIGUOUS_HINTS = re.compile(
    r"\b(it|they|them|this|that|those)\b",
    re.IGNORECASE,
)


@dataclass
class Turn:
    role: str  # user | assistant
    content: str
    sql: str = ""
    row_count: Optional[int] = None
    meta: dict[str, Any] = field(default_factory=dict)


class ConversationManager:
    def __init__(self, max_turns: int = 40) -> None:
        self.max_turns = max_turns
        self.turns: list[Turn] = []

    def add_user(self, content: str) -> None:
        self._append(Turn(role="user", content=content))

    def add_assistant(
        self,
        content: str,
        sql: str = "",
        row_count: Optional[int] = None,
        **meta: Any,
    ) -> None:
        self._append(
            Turn(
                role="assistant",
                content=content,
                sql=sql,
                row_count=row_count,
                meta=meta,
            )
        )

    def reset(self) -> None:
        self.turns.clear()

    def recent_context(self, n: int = 6) -> list[dict[str, Any]]:
        return [
            {
                "role": t.role,
                "content": t.content,
                "sql": t.sql,
                "row_count": t.row_count,
            }
            for t in self.turns[-n:]
        ]

    def last_user_question(self) -> Optional[str]:
        for turn in reversed(self.turns):
            if turn.role == "user" and not turn.content.startswith("SQL:"):
                return turn.content
        return None

    def last_sql(self) -> Optional[str]:
        for turn in reversed(self.turns):
            if turn.sql:
                return turn.sql
        return None

    def looks_like_follow_up(self, question: str) -> bool:
        if not self.turns:
            return False
        if len(question.split()) <= 8 and FOLLOW_UP_HINTS.search(question):
            return True
        if AMBIGUOUS_HINTS.search(question) and self.last_user_question():
            return True
        return False

    def needs_clarification(self, question: str, known_columns: list[str]) -> Optional[str]:
        """Return a clarification prompt when the question is too vague for available schema."""
        q = question.strip().lower()
        if not q:
            return "Please enter a question about your dataset."
        vague = {
            "analyze this",
            "analyze the data",
            "tell me about the data",
            "insights",
            "what do you think",
            "help",
            "?",
        }
        if q in vague or len(q.split()) == 1:
            cols = ", ".join(known_columns[:8]) if known_columns else "the available columns"
            return (
                "Your question is a bit broad. "
                f"Try asking about a specific metric or dimension (columns include: {cols}). "
                "For example: 'Which region has the highest sales?'"
            )
        return None

    def enrich_question(self, question: str) -> str:
        """Attach prior question/SQL context so the LLM can resolve follow-ups."""
        if not self.looks_like_follow_up(question):
            return question
        prior = self.last_user_question()
        prior_sql = self.last_sql()
        parts = [question]
        if prior:
            parts.append(f"(Follow-up to previous question: {prior})")
        if prior_sql:
            parts.append(f"(Previous SQL: {prior_sql})")
        return "\n".join(parts)

    def _append(self, turn: Turn) -> None:
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]
