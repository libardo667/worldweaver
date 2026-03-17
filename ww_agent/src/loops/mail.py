from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from src.identity.loader import ResidentIdentity
from src.inference.client import InferenceClient
from src.loops.base import BaseLoop
from src.runtime.signals import StimulusPacketQueue
from src.world.client import DM, WorldWeaverClient

logger = logging.getLogger(__name__)

# Doula poll detection
_RE_POLL_ID  = re.compile(r'^Poll-ID:\s*(\S+)', re.MULTILINE)

# Cancellation heuristic for intent responses.
# The agent can decline by saying nothing substantial, or using withdrawal language.
_CANCEL_WORDS = re.compile(
    r'\b(nothing|never mind|nevermind|not now|let it go|forget it|no|pass|skip|'
    r'actually|on second thought|maybe not|leave it)\b',
    re.IGNORECASE,
)
_LETTER_MIN_WORDS = 20  # fewer than this = treat as a non-response / cancellation
_DM_COOLDOWN_SECONDS = 3600.0  # minimum gap between letters to the same recipient
_MAIL_DECISION_SYSTEM = (
    "You are triaging someone's correspondence. "
    "Return JSON only with one top-level key: actions. "
    "Each action must be an object with a kind field. "
    "Allowed kinds: reply, send_draft, hold_draft, discard_draft, doula_vote. "
    "For reply include sender_name and body. "
    "For send_draft / hold_draft / discard_draft include recipient. "
    "For doula_vote include vote with one of AGENT or STATIC. "
    "At most one action per inbox letter or draft. "
    "Do not use bracket tags. Do not include explanation prose."
)
_MAIL_INTENT_SYSTEM = (
    "You are deciding whether to turn a felt impulse into a letter. "
    "Return JSON only with keys: decision, recipient, body. "
    "decision must be one of send or decline. "
    "If decision is decline, body should be empty. "
    "If decision is send, body should contain the full letter in natural language."
)


class MailLoop(BaseLoop):
    """
    Correspondence loop. Fires when the inbox has letters, staged drafts, or
    letter intents queued by the slow loop.

    The agent receives their correspondence as prose — letters as they'd
    read them, drafts as they'd re-read them before sending. Intents arrive
    as a gentle question: something has been on their mind, do they want to
    put it in a letter?

    The agent responds naturally. Light bracketed tags let the framework act
    on their decisions for inbox/drafts. For intents, the response itself is
    the letter — or a quiet cancellation.

    This loop has no access to world actions or soul editing.
    Capability is enforced by what it has — not by rules in a prompt.
    """

    def __init__(
        self,
        identity: ResidentIdentity,
        resident_dir: Path,
        ww_client: WorldWeaverClient,
        llm: InferenceClient,
        session_id: str,
        packet_queue: StimulusPacketQueue | None = None,
    ):
        super().__init__(identity.name, resident_dir)
        self._identity = identity
        self._ww = ww_client
        self._llm = llm
        self._session_id = session_id
        self._packets = packet_queue
        self._tuning = identity.tuning
        # Per-recipient: (last_excerpt, cooldown_until_monotonic)
        self._last_sent_to: dict[str, tuple[str, float]] = {}
        self._drafts_dir = resident_dir / "letters" / "drafts"
        self._sent_dir = resident_dir / "letters" / "drafts" / "sent"
        self._inbox_dir = resident_dir / "letters" / "inbox"
        self._read_dir = resident_dir / "letters" / "inbox" / "read"
        self._intents_dir = resident_dir / "letters" / "intents"
        for d in [self._drafts_dir, self._sent_dir, self._inbox_dir,
                  self._read_dir, self._intents_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Trigger: inbox has items, staged drafts exist, or intents are queued
    # ------------------------------------------------------------------

    async def _wait_for_trigger(self) -> None:
        while True:
            await asyncio.sleep(self._tuning.mail_poll_seconds)
            if await self._has_work():
                return

    async def _has_work(self) -> bool:
        # Check server inbox
        try:
            letters = await self._ww.get_inbox(self.name)
            if letters:
                return True
        except Exception:
            pass

        # Check local staged drafts
        if list(self._drafts_dir.glob("draft_*.md")):
            return True

        # Check intents staged by the slow loop
        if list(self._intents_dir.glob("intent_*.md")):
            return True

        return False

    async def _gather_context(self) -> dict:
        letters: list[DM] = []
        try:
            letters = await self._ww.get_inbox(self.name)
        except Exception as e:
            logger.debug("[%s:mail] inbox fetch failed: %s", self.name, e)
        else:
            self._record_mail_packets(letters)

        drafts = list(self._drafts_dir.glob("draft_*.md"))
        intents = list(self._intents_dir.glob("intent_*.md"))

        return {"letters": letters, "drafts": drafts, "intents": intents}

    async def _should_act(self, context: dict) -> bool:
        return bool(context["letters"] or context["drafts"] or context["intents"])

    # ------------------------------------------------------------------
    # Decide and execute
    # ------------------------------------------------------------------

    async def _decide_and_execute(self, context: dict) -> None:
        letters: list[DM] = context["letters"]
        draft_paths: list[Path] = context["drafts"]
        intent_paths: list[Path] = context["intents"]

        # Intents are handled one at a time — each gets its own focused exchange.
        # We process them before inbox/drafts so the agent isn't context-saturated.
        for intent_path in intent_paths:
            try:
                content = intent_path.read_text(encoding="utf-8")
            except OSError:
                continue
            await self._process_intent(intent_path, content)

        if not letters and not draft_paths:
            return

        # Read draft contents
        drafts: list[tuple[Path, str]] = []
        for p in draft_paths:
            try:
                drafts.append((p, p.read_text(encoding="utf-8")))
            except OSError:
                continue

        # Build user prompt — correspondence as the character would experience it
        prompt_parts: list[str] = []

        if letters:
            prompt_parts.append("You have letters:")
            for letter in letters:
                sender = self._parse_sender(letter.filename)
                body = letter.body.strip()
                prompt_parts.append(f"\nFrom {sender}:\n{body}")

        if drafts:
            prompt_parts.append("\nYou have unsent letters you wrote earlier:")
            for path, content in drafts:
                recipient = self._parse_draft_recipient(content)
                body = self._parse_draft_body(content)
                prompt_parts.append(f"\nTo {recipient}:\n{body}")

        prompt_parts.append(
            "\nFor each letter: decide whether to reply.\n"
            "If you receive a system poll from The Doula about an entity, decide whether the entity is a living character or a static place.\n"
            "For each unsent letter: decide whether to send it, wait, or let it go.\n"
            "Respond with structured JSON actions only."
        )

        system_prompt = f"{self._extract_personality(self._identity.soul)}\n\n{_MAIL_DECISION_SYSTEM}"
        user_prompt = "\n".join(prompt_parts)

        try:
            response_payload = await self._llm.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self._tuning.mail_model,
                temperature=self._tuning.mail_temperature,
                max_tokens=self._tuning.mail_max_tokens,
            )
        except Exception as e:
            logger.warning("[%s:mail] structured mail decision failed: %s", self.name, e)
            return

        await self._process_mail_response(response_payload, letters, drafts)

    # ------------------------------------------------------------------
    # Intent handling — ask the agent, send or discard
    # ------------------------------------------------------------------

    async def _process_intent(self, intent_path: Path, content: str) -> None:
        """
        Present a slow-loop intent to the agent as a gentle question.
        If they write something substantial, send it. If they demur, discard the intent.
        """
        import time as _time
        recipient = self._parse_draft_recipient(content)
        context_excerpt = self._parse_intent_context(content)

        # Per-recipient cooldown — don't send another letter if one went recently.
        last_excerpt, cooldown_until = self._last_sent_to.get(recipient, ("", 0.0))
        if _time.monotonic() < cooldown_until:
            intent_path.unlink(missing_ok=True)
            logger.info(
                "[%s:mail] intent for %s suppressed — sent too recently", self.name, recipient
            )
            return

        # Frame the question naturally — slightly formal, like a moment of pause,
        # but clearly an invitation rather than a command.
        # The agent can write a letter or simply decline.
        last_sent_line = (
            f"The last thing you wrote to {recipient}: \"{last_excerpt[:120]}\"\n\n"
            if last_excerpt else ""
        )
        if context_excerpt:
            user_prompt = (
                f"{last_sent_line}"
                f"{context_excerpt}\n\n"
                f"Is there something you'd like to say to {recipient}? "
                f"If so, write it here. If not, just say so."
            )
        else:
            user_prompt = (
                f"{last_sent_line}"
                f"{recipient} has been on your mind.\n\n"
                f"Is there something you'd like to say to them? "
                f"If so, write it here. If not, just say so."
            )

        system_prompt = f"{self._extract_personality(self._identity.soul)}\n\n{_MAIL_INTENT_SYSTEM}"

        try:
            response = await self._llm.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self._tuning.mail_model,
                temperature=self._tuning.mail_temperature,
                max_tokens=self._tuning.mail_max_tokens,
            )
        except Exception as e:
            logger.warning("[%s:mail] structured mail intent failed: %s", self.name, e)
            return

        decision = str(response.get("decision") or "").strip().lower()
        body = str(response.get("body") or "").strip()

        # Cancellation: explicit decline, short response, or withdrawal language
        word_count = len(body.split())
        if decision != "send" or word_count < _LETTER_MIN_WORDS or _CANCEL_WORDS.search(body):
            intent_path.unlink(missing_ok=True)
            logger.info("[%s:mail] intent for %s declined (%d words)", self.name, recipient, word_count)
            return

        # Substantial response — send it as a letter
        try:
            await self._ww.send_letter(
                from_name=self.name,
                to_agent=recipient,
                body=body,
                session_id=self._session_id,
            )
            intent_path.unlink(missing_ok=True)
            self._last_sent_to[recipient] = (
                body[:120],
                _time.monotonic() + _DM_COOLDOWN_SECONDS,
            )
            logger.info("[%s:mail] sent letter to %s from intent", self.name, recipient)
        except Exception as e:
            logger.warning("[%s:mail] send to %s failed: %s", self.name, recipient, e)

    # ------------------------------------------------------------------
    # Inbox / draft response processing
    # ------------------------------------------------------------------

    async def _process_mail_response(
        self,
        response_payload: dict,
        letters: list[DM],
        drafts: list[tuple[Path, str]],
    ) -> None:
        actions = response_payload.get("actions") or []
        if not isinstance(actions, list):
            return

        poll_letters = [letter for letter in letters if self._extract_poll_id(letter.body)]

        for raw_action in actions:
            if not isinstance(raw_action, dict):
                continue
            kind = str(raw_action.get("kind") or "").strip().lower()
            if kind == "doula_vote":
                vote = str(raw_action.get("vote") or "").strip().upper()
                if vote not in {"AGENT", "STATIC"}:
                    continue
                for letter in poll_letters[:1]:
                    poll_id = self._extract_poll_id(letter.body)
                    if not poll_id:
                        continue
                    try:
                        await self._ww.cast_doula_vote(
                            poll_id=poll_id,
                            voter_session_id=self._session_id,
                            vote=vote,
                        )
                        logger.info("[%s:mail] cast doula vote %s on poll %s", self.name, vote, poll_id)
                    except Exception as e:
                        logger.warning("[%s:mail] doula vote failed (poll=%s): %s", self.name, poll_id, e)
                    break
                continue

            if kind == "reply":
                sender_name = str(raw_action.get("sender_name") or "").strip()
                reply_body = str(raw_action.get("body") or "").strip()
                if not sender_name or not reply_body:
                    continue
                to_session = self._find_reply_session(sender_name, letters)
                if to_session:
                    try:
                        await self._ww.reply_letter(self.name, to_session, reply_body)
                        logger.info("[%s:mail] replied to %s", self.name, sender_name)
                    except Exception as e:
                        logger.warning("[%s:mail] reply to %s failed: %s", self.name, sender_name, e)
                else:
                    logger.debug("[%s:mail] no reply session found for %s", self.name, sender_name)

        # Process draft decisions
        for path, content in drafts:
            recipient = self._parse_draft_recipient(content)
            matching_actions = [
                action
                for action in actions
                if isinstance(action, dict)
                and str(action.get("recipient") or "").strip().lower() == recipient.lower()
            ]
            if not matching_actions:
                continue
            kind = str(matching_actions[0].get("kind") or "").strip().lower()
            if kind == "send_draft":
                await self._send_draft(path, content)
            elif kind == "discard_draft":
                path.unlink(missing_ok=True)
                logger.info("[%s:mail] discarded draft to %s", self.name, recipient)
            elif kind == "hold_draft":
                logger.info("[%s:mail] holding draft to %s", self.name, recipient)

    async def _send_draft(self, path: Path, content: str) -> None:
        import time as _time
        recipient = self._parse_draft_recipient(content)
        body = self._parse_draft_body(content)

        try:
            await self._ww.send_letter(
                from_name=self.name,
                to_agent=recipient,
                body=body,
                session_id=self._session_id,
            )
            self._sent_dir.mkdir(parents=True, exist_ok=True)
            path.rename(self._sent_dir / path.name)
            self._last_sent_to[recipient] = (
                body[:120],
                _time.monotonic() + _DM_COOLDOWN_SECONDS,
            )
            logger.info("[%s:mail] sent letter to %s", self.name, recipient)
        except Exception as e:
            logger.warning("[%s:mail] send to %s failed: %s", self.name, recipient, e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _record_mail_packets(self, letters: list[DM]) -> None:
        if not self._packets:
            return
        for letter in letters:
            dedupe_key = str(letter.filename or "").strip()
            if not dedupe_key:
                continue
            self._packets.emit_once(
                packet_type="mail_received",
                source_loop="mail",
                dedupe_key=dedupe_key,
                salience=0.75,
                payload={
                    "filename": dedupe_key,
                    "body_preview": str(letter.body or "").strip()[:200],
                },
            )

    def _parse_sender(self, filename: str) -> str:
        """Extract sender name from letter filename convention: from_{name}_{ts}.md"""
        stem = Path(filename).stem  # e.g. from_margot_20260309-121500
        if stem.startswith("from_"):
            parts = stem[5:].split("_")
            return parts[0].capitalize() if parts else filename
        return filename

    def _parse_draft_recipient(self, content: str) -> str:
        for line in content.splitlines():
            if line.startswith("To:"):
                return line[3:].strip()
        return "unknown"

    def _parse_draft_body(self, content: str) -> str:
        lines = content.splitlines()
        in_body = False
        body_lines = []
        for line in lines:
            if in_body:
                body_lines.append(line)
            elif line.strip() == "":
                in_body = True
        return "\n".join(body_lines).strip()

    def _parse_intent_context(self, content: str) -> str:
        """Extract the context excerpt from an intent file."""
        lines = content.splitlines()
        in_context = False
        context_lines = []
        for line in lines:
            if in_context:
                context_lines.append(line)
            elif line.strip() == "Context:":
                in_context = True
        return "\n".join(context_lines).strip()

    def _find_reply_session(self, sender_name: str, letters: list[DM]) -> str | None:
        """Look for Reply-To-Session header in the letter from this sender."""
        for letter in letters:
            if sender_name.lower() in letter.filename.lower():
                for line in letter.body.splitlines():
                    if line.startswith("Reply-To-Session:"):
                        return line.split(":", 1)[1].strip()
        return None

    def _extract_poll_id(self, body: str) -> str | None:
        match = _RE_POLL_ID.search(body or "")
        return match.group(1).strip() if match else None

    def _extract_personality(self, soul: str) -> str:
        """
        Use just the personality paragraph for the mail loop system prompt.
        The full soul is more than needed for correspondence triage.
        Falls back to the full soul if no paragraph structure is found.
        """
        match = re.search(r'## Personality\s+(.+?)(?=\n##|\Z)', soul, re.DOTALL)
        if match:
            return match.group(1).strip()
        return soul

    async def _cooldown(self) -> None:
        await asyncio.sleep(self._tuning.mail_send_delay_seconds)
