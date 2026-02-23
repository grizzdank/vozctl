"""Intent parser: unified dispatch replacing modal COMMAND/DICTATION state machine.

Fast path handles exact/parameterized/formatter/NATO matches with zero added latency.
SLM slow path (Haiku API) fires only for mixed/ambiguous utterances.
Falls back to rule-based matching if SLM fails or is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)


# ── Action / Result dataclasses ───────────────────────────────


@dataclass
class Action:
    """Single atomic action to execute."""
    kind: str        # "command", "dictation", "punctuation", "format"
    name: str        # command name or description
    args: dict = field(default_factory=dict)
    text: str = ""   # for dictation/format: the text to type
    handler: Callable | None = None  # resolved handler (set by fast path or executor)


@dataclass
class IntentResult:
    """Result of parsing an utterance into actions."""
    actions: list[Action]
    source: str       # "fast_path", "slm", "fallback"
    latency_ms: float = 0.0


# ── Intent Parser ─────────────────────────────────────────────


class IntentParser:
    """Parse transcripts into Action sequences.

    Args:
        use_slm: Whether to call the SLM for ambiguous utterances.
    """

    def __init__(self, use_slm: bool = True):
        self._use_slm = use_slm and bool(os.environ.get("ANTHROPIC_API_KEY"))
        self._slm_client = None
        if self._use_slm:
            try:
                import anthropic
                self._slm_client = anthropic.Anthropic()
                log.info("SLM enabled (Haiku API)")
            except Exception as e:
                log.warning("SLM unavailable: %s — running rules-only", e)
                self._use_slm = False
        else:
            log.info("SLM disabled — running rules-only")

    def parse(self, transcript: str, context=None) -> IntentResult:
        """Parse a transcript into a list of actions.

        Fast path: exact → parameterized → formatter → NATO → single-command match.
        If fast path matches, return immediately (0ms added latency).
        Otherwise: SLM call (if enabled) → fallback to rules.
        """
        t0 = time.monotonic()

        # Fast path — try rule-based matching first
        result = self._fast_path(transcript)
        if result:
            result.latency_ms = (time.monotonic() - t0) * 1000
            return result

        # SLM slow path — only for mixed/ambiguous utterances
        if self._use_slm:
            result = self._slm_path(transcript, context)
            if result:
                result.latency_ms = (time.monotonic() - t0) * 1000
                return result

        # Fallback — use existing match() as catch-all
        result = self._fallback(transcript)
        result.latency_ms = (time.monotonic() - t0) * 1000
        return result

    def _fast_path(self, transcript: str) -> IntentResult | None:
        """Try to match as a single known command. Returns None if ambiguous."""
        from vozctl.commands import (
            _EXACT, _PARAMETERIZED, _normalize, _try_nato_sequence,
            _INSERT_AS_KEY, _type_formatted, cmd_type_text,
        )
        from vozctl.formatters import try_format

        # Handle "type X" / "insert X" with original casing preserved
        raw_m = re.match(r"^\s*(?:type|insert)\s+(?P<text>.+?)\s*$", transcript, re.IGNORECASE)
        if raw_m:
            text = raw_m.group("text")
            text_norm = _normalize(text)
            if text_norm in _INSERT_AS_KEY:
                return IntentResult(
                    actions=[Action(
                        kind="command", name=f"insert:{text_norm}",
                        handler=_INSERT_AS_KEY[text_norm],
                    )],
                    source="fast_path",
                )
            return IntentResult(
                actions=[Action(
                    kind="command", name="type_text",
                    args={"text": text}, text=text,
                    handler=lambda t=text: cmd_type_text(text=t),
                )],
                source="fast_path",
            )

        normalized = _normalize(transcript)

        # 1. Exact match
        if normalized in _EXACT:
            log.info("Intent [fast/exact]: %s", normalized)
            return IntentResult(
                actions=[Action(
                    kind="command", name=normalized,
                    handler=_EXACT[normalized],
                )],
                source="fast_path",
            )

        # 2. Parameterized match
        for pattern, name, handler in _PARAMETERIZED:
            m = pattern.match(normalized)
            if m:
                args = m.groupdict()
                log.info("Intent [fast/param]: %s → %s", name, args)
                return IntentResult(
                    actions=[Action(
                        kind="command", name=name,
                        args=args,
                        handler=lambda h=handler, a=args: h(**a),
                    )],
                    source="fast_path",
                )

        # 3. Formatter match
        fmt_result = try_format(normalized)
        if fmt_result:
            formatted, fmt_name = fmt_result
            log.info("Intent [fast/formatter]: %s → %r", fmt_name, formatted)
            return IntentResult(
                actions=[Action(
                    kind="format", name=f"format:{fmt_name}",
                    text=formatted,
                    handler=lambda f=formatted: _type_formatted(f),
                )],
                source="fast_path",
            )

        # 4. NATO sequence
        nato_result = _try_nato_sequence(normalized)
        if nato_result:
            log.info("Intent [fast/nato]: %r → %r", normalized, nato_result)
            return IntentResult(
                actions=[Action(
                    kind="command", name="nato_sequence",
                    text=nato_result,
                    handler=lambda t=nato_result: _type_formatted(t),
                )],
                source="fast_path",
            )

        # 5. Multi-sentence split (Parakeet adds punctuation)
        sentences = re.split(r'[.!?,;]+', transcript)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 1:
            actions = []
            for sent in sentences:
                sub_result = self._match_single_normalized(_normalize(sent))
                if sub_result:
                    actions.append(sub_result)
            if actions:
                log.info("Intent [fast/multi]: %d actions", len(actions))
                return IntentResult(actions=actions, source="fast_path")

        # Fast path couldn't handle it — return None to try SLM
        return None

    def _match_single_normalized(self, normalized: str) -> Action | None:
        """Match a single normalized phrase to an Action. Returns None if no match."""
        from vozctl.commands import _EXACT, _PARAMETERIZED, _try_nato_sequence, _type_formatted
        from vozctl.formatters import try_format

        if not normalized:
            return None

        if normalized in _EXACT:
            return Action(kind="command", name=normalized, handler=_EXACT[normalized])

        for pattern, name, handler in _PARAMETERIZED:
            m = pattern.match(normalized)
            if m:
                args = m.groupdict()
                return Action(kind="command", name=name, args=args,
                              handler=lambda h=handler, a=args: h(**a))

        fmt_result = try_format(normalized)
        if fmt_result:
            formatted, fmt_name = fmt_result
            return Action(kind="format", name=f"format:{fmt_name}", text=formatted,
                          handler=lambda f=formatted: _type_formatted(f))

        nato_result = _try_nato_sequence(normalized)
        if nato_result:
            return Action(kind="command", name="nato_sequence", text=nato_result,
                          handler=lambda t=nato_result: _type_formatted(t))

        return None

    def _slm_path(self, transcript: str, context) -> IntentResult | None:
        """Call SLM to parse ambiguous/mixed utterances into action sequences."""
        if not self._slm_client:
            return None

        try:
            system_prompt = self._build_system_prompt(context)
            response = self._slm_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system=system_prompt,
                messages=[{"role": "user", "content": transcript}],
                timeout=0.6,  # 600ms hard timeout
            )
            raw = response.content[0].text.strip()
            actions = self._parse_slm_response(raw, transcript)
            if actions:
                log.info("Intent [slm]: %d actions from %r", len(actions), transcript)
                return IntentResult(actions=actions, source="slm")
        except Exception as e:
            log.warning("SLM call failed: %s — falling back to rules", e)

        return None

    def _build_system_prompt(self, context=None) -> str:
        """Build compact system prompt with command catalog for the SLM."""
        app_ctx = ""
        if context:
            app_ctx = f"\nActive app: {context.app_name} ({context.bundle_id})"

        return f"""You are a voice command parser for a developer voice control tool.

Given a voice transcript, output ONLY a JSON array of actions. No explanation.

Commands available:
- Navigation: go {{up,down,left,right}}, go N {{direction}}, word {{left,right}}, N words {{direction}}, page up/down, head, tail, home, end, go to line N
- Editing: delete, delete word, delete N, delete N words, backspace, undo, redo, cut, copy, paste, save
- Selection: select all, select line, select word {{direction}}, select N {{direction}}
- Text: type <text>, insert <text>
- Formatting: snake/camel/pascal/kebab/constant <words> (outputs formatted identifier)
- Terminal: cancel, clear, exit, tab, escape, enter, space
- Tabs: new tab, close tab, next tab, previous tab
- Panes: focus {{left,right,up,down}}
- Safety: scratch that (undo last typed text)

Action JSON format:
{{"kind":"command","name":"<command name>","args":{{}}}}
{{"kind":"dictation","text":"<text to type>"}}

Examples:
"delete two words and type hello" → [{{"kind":"command","name":"delete_words","args":{{"count":"two"}}}},{{"kind":"dictation","text":"hello"}}]
"save and close tab" → [{{"kind":"command","name":"save"}},{{"kind":"command","name":"close tab"}}]
"go three up then type done" → [{{"kind":"command","name":"go_n_direction","args":{{"count":"three","direction":"up"}}}},{{"kind":"dictation","text":"done"}}]
{app_ctx}"""

    def _parse_slm_response(self, raw: str, transcript: str) -> list[Action] | None:
        """Parse SLM JSON response into Action objects with resolved handlers."""
        try:
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            if not isinstance(data, list):
                return None
        except (json.JSONDecodeError, ValueError):
            log.warning("SLM returned invalid JSON: %r", raw[:200])
            return None

        actions = []
        for item in data:
            kind = item.get("kind", "")
            if kind == "command":
                action = self._resolve_command_action(item)
                if action:
                    actions.append(action)
            elif kind == "dictation":
                text = item.get("text", "")
                if text:
                    from vozctl.commands import _type_dictation
                    actions.append(Action(
                        kind="dictation", name="dictation", text=text,
                        handler=lambda t=text: _type_dictation(t),
                    ))

        return actions if actions else None

    def _resolve_command_action(self, item: dict) -> Action | None:
        """Resolve an SLM command action to an executable handler."""
        from vozctl.commands import _EXACT, _PARAMETERIZED, _normalize

        name = item.get("name", "")
        args = item.get("args", {})
        normalized = _normalize(name)

        # Try exact match first
        if normalized in _EXACT:
            return Action(kind="command", name=normalized, handler=_EXACT[normalized])

        # Try parameterized — reconstruct the full command string for regex matching
        # e.g. name="go_n_direction" args={"count":"three","direction":"up"} → "go three up"
        # Build candidate strings from the args
        candidates = [normalized]
        if args:
            # Try "name arg1 arg2" style
            arg_str = " ".join(str(v) for v in args.values())
            candidates.append(f"{normalized} {arg_str}")
            # Try just the arg values joined (for commands like "delete two words")
            candidates.append(arg_str)
            # Try reconstructing common patterns
            count = args.get("count", "")
            direction = args.get("direction", "")
            if count and direction:
                candidates.append(f"go {count} {direction}")
                candidates.append(f"{count} words {direction}")
                candidates.append(f"delete {count} words")
                candidates.append(f"delete {count}")
                candidates.append(f"select {count} {direction}")

        for candidate in candidates:
            for pattern, pname, handler in _PARAMETERIZED:
                m = pattern.match(candidate)
                if m:
                    matched_args = m.groupdict()
                    return Action(kind="command", name=pname, args=matched_args,
                                  handler=lambda h=handler, a=matched_args: h(**a))

        log.warning("SLM command %r not resolved — skipping", name)
        return None

    def _fallback(self, transcript: str) -> IntentResult:
        """Last resort: type as dictation."""
        from vozctl.commands import _type_dictation
        log.info("Intent [fallback/dictation]: %r", transcript)
        return IntentResult(
            actions=[Action(
                kind="dictation", name="dictation",
                text=transcript,
                handler=lambda t=transcript: _type_dictation(t),
            )],
            source="fallback",
        )


# ── Action Executor ───────────────────────────────────────────


def execute_actions(result: IntentResult) -> None:
    """Execute a list of actions from an IntentResult."""
    for action in result.actions:
        try:
            if action.handler:
                action.handler()
            else:
                log.warning("Action %r has no handler, skipping", action.name)
        except Exception as e:
            log.error("Action %r failed: %s", action.name, e)
