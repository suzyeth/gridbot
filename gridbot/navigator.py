"""State-graph navigation driven by a YAML-described screen map.

The navigator answers one question repeatedly: *"I want to be on screen X — given
where I am right now, what's the shortest sequence of UI actions that gets me
there?"*

Workflow:

1. Author a YAML file describing every screen, what its outgoing transitions
   look like (which button/gesture/key takes you to which next screen), and how
   long to wait for each transition to complete.
2. Load it with :func:`load_screens`.
3. Wrap your :class:`gridbot.AdbCapture` / :class:`gridbot.AdbInput` /
   :class:`gridbot.StateDetector` in a :class:`NavigatorContext`.
4. Call :meth:`Navigator.goto("target_screen")` and let it BFS to the target.

YAML shape:

.. code-block:: yaml

    states:
      main_menu:
        description: Top-level menu.
        transitions:
          - to: settings_screen
            action: { type: tap_text, text: "Settings" }
            wait_for_change_sec: 3
          - to: inventory_screen
            action: { type: tap_text, text: "Inventory", fallback_coords: [540, 1850] }
      settings_screen:
        transitions:
          - to: main_menu
            action: { type: keyevent, key: "BACK" }

The state names referenced here must match those in your
:class:`gridbot.StateDetector` rule list — :class:`Navigator` validates this on
construction.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Annotated, Dict, List, Literal, Optional, Tuple, Union

import yaml
from loguru import logger
from pydantic import BaseModel, Field

from gridbot.capture import AdbCapture
from gridbot.input import AdbInput
from gridbot.ocr import OcrEngine
from gridbot.state import StateDetector


class NavigatorError(Exception):
    """Raised when navigation cannot proceed (bad config, no path, dead end, etc.)."""


# ============ Action types (discriminated union by `type`) ============


class TapTextAction(BaseModel):
    """Find ``text`` on screen via OCR, then tap its centre.

    Match strategy in order:

    1. Fast OCR — if a match is found, tap and return.
    2. If fast OCR misses but ``fallback_coords`` is set, tap those coords.
    3. If still no hit and the navigator was given an ``ocr_accurate`` engine,
       try the accurate (server) model. Otherwise fail.

    Setting ``fallback_coords`` after you've measured a button's stable
    location dramatically cuts worst-case latency, since the slow accurate
    path can take 30–60 seconds on CPU.
    """
    type: Literal["tap_text"]
    text: str
    exact: bool = False
    min_confidence: float = 0.7
    fallback_coords: Optional[List[int]] = None
    """``[x, y]``. Tapped when fast OCR misses ``text``, before falling back to accurate OCR."""


class TapCoordsAction(BaseModel):
    """Tap a fixed coordinate. Use when the button's position is reliable."""
    type: Literal["tap_coords"]
    x: int
    y: int


class KeyeventAction(BaseModel):
    """Send an Android system key (BACK or HOME)."""
    type: Literal["keyevent"]
    key: Literal["BACK", "HOME"]


class SwipeAction(BaseModel):
    """Swipe gesture from ``(x1, y1)`` to ``(x2, y2)`` over ``duration_ms`` ms."""
    type: Literal["swipe"]
    x1: int
    y1: int
    x2: int
    y2: int
    duration_ms: int = 300


class WaitUntilAction(BaseModel):
    """No-op — wait for the state to change on its own (animation, server roundtrip, ...)."""
    type: Literal["wait_until"]


Action = Annotated[
    Union[TapTextAction, TapCoordsAction, KeyeventAction, SwipeAction, WaitUntilAction],
    Field(discriminator="type"),
]


# ============ Transition / State / config root ============


class Transition(BaseModel):
    """One outgoing edge from a state.

    Says: *"if you execute :attr:`action` while in the source state, you should
    end up in :attr:`to` within :attr:`wait_for_change_sec` seconds."*
    """
    to: str
    action: Action
    wait_for_change_sec: float = 3.0
    description: Optional[str] = None


class StateConfig(BaseModel):
    """Per-state configuration block in ``screens.yaml``."""
    description: Optional[str] = None
    transitions: List[Transition] = Field(default_factory=list)


class ScreensConfig(BaseModel):
    """Root model for ``screens.yaml``."""
    states: Dict[str, StateConfig]


# ============ Loading + the Navigator itself ============


def load_screens(path: Union[str, Path]) -> ScreensConfig:
    """Load and validate a ``screens.yaml`` file.

    Args:
        path: Required — there is no default location, since gridbot ships
            no app-specific config.

    Raises:
        NavigatorError: If the file is missing or fails schema validation.
    """
    path = Path(path)
    if not path.exists():
        raise NavigatorError(f"screens.yaml not found at: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        return ScreensConfig.model_validate(raw)
    except Exception as e:
        raise NavigatorError(f"screens.yaml validation failed: {e}") from e


@dataclass
class NavigatorContext:
    """Dependencies the :class:`Navigator` needs to do its job.

    Args:
        capture: For taking screenshots when detecting the current state and
            for sourcing images for ``tap_text`` actions.
        input: For sending taps / swipes / key events.
        state: For classifying screenshots into named states. The list of valid
            state names is derived from this detector's rules.
        ocr_accurate: Optional second OCR engine, typically a non-fast (server)
            instance. Used as a last-resort fallback when ``tap_text`` misses
            with both fast OCR and ``fallback_coords``. ``None`` disables the
            slow fallback entirely.
        cancel_event: Optional :class:`threading.Event`. If set during a
            :meth:`Navigator.goto` call, navigation aborts cooperatively at the
            next checkpoint and ``goto`` returns ``False``.
    """
    capture: AdbCapture
    input: AdbInput
    state: StateDetector
    ocr_accurate: Optional[OcrEngine] = None
    cancel_event: Optional[Event] = None


class Navigator:
    """BFS-driven UI navigator over a screen state graph.

    Args:
        config: Output of :func:`load_screens`.
        ctx: The capture / input / state-detection bundle. See
            :class:`NavigatorContext`.

    Raises:
        NavigatorError: If the YAML references a state that the detector's
            rule list doesn't know about, or a transition's ``to`` field
            points at an unknown state.
    """

    #: If the same ``(current_state, action_type)`` pair fires this many
    #: times in a row without producing a state change, give up early
    #: instead of burning the whole step budget on a dead transition.
    DEAD_TRANSITION_LIMIT = 2

    def __init__(self, config: ScreensConfig, ctx: NavigatorContext):
        self.config = config
        self.ctx = ctx
        self._validate()

    def _validate(self) -> None:
        valid_states = {r.name for r in self.ctx.state.rules} | {StateDetector.UNKNOWN}

        for state_name, state_cfg in self.config.states.items():
            if state_name not in valid_states:
                raise NavigatorError(
                    f"screens.yaml references unknown state: {state_name!r}. "
                    f"Known states (from StateDetector rules): {sorted(valid_states)}"
                )
            for t in state_cfg.transitions:
                if t.to not in valid_states:
                    raise NavigatorError(
                        f"transition target unknown: {t.to!r} "
                        f"(from state {state_name!r})"
                    )

        n_transitions = sum(len(s.transitions) for s in self.config.states.values())
        logger.info(
            f"Navigator loaded: {len(self.config.states)} states, "
            f"{n_transitions} transitions"
        )

    # ----- State detection -----

    def detect_current(self) -> str:
        """Capture a screenshot and classify the current state."""
        img = self.ctx.capture.screenshot()
        return self.ctx.state.detect(img)

    # ----- BFS path-finding (no execution) -----

    def find_path(
        self, src: str, dst: str
    ) -> Optional[List[Tuple[str, Transition]]]:
        """Return the shortest path from ``src`` to ``dst``, or ``None`` if unreachable.

        Returns:
            ``None`` — no path exists.
            ``[]`` — already at ``dst``.
            Otherwise — a list of ``(next_state, transition)`` pairs in order.
        """
        if src == dst:
            return []
        if src not in self.config.states:
            return None  # current state isn't on the graph at all

        visited = {src}
        queue: deque = deque([(src, [])])

        while queue:
            current, path = queue.popleft()
            for trans in self.config.states[current].transitions:
                if trans.to in visited:
                    continue
                new_path = path + [(trans.to, trans)]
                if trans.to == dst:
                    return new_path
                if trans.to in self.config.states:
                    visited.add(trans.to)
                    queue.append((trans.to, new_path))

        return None

    # ----- Actually navigate -----

    def goto(self, target: str, max_steps: int = 10) -> bool:
        """Drive the device from the current state to ``target``.

        Each step:

        1. Detect the current state.
        2. If it equals ``target``, success.
        3. BFS for a path; if none exists, fail.
        4. Execute the first action of the path and wait for the expected
           state change.

        Dead-end protection: if the same ``(state, action_type)`` pair fires
        :attr:`DEAD_TRANSITION_LIMIT` times in a row without changing state,
        ``goto`` aborts immediately rather than wasting the rest of the step
        budget. Almost always indicates a stale ``screens.yaml`` transition.

        Returns:
            ``True`` on arrival, ``False`` on failure / cancellation / step
            budget exhaustion / dead transition.
        """
        logger.info(f"Navigator.goto({target!r})")

        last_signature: Optional[Tuple[str, str]] = None
        stuck_count = 0

        for step_idx in range(1, max_steps + 1):
            if self._cancelled():
                logger.warning("cancel_event set — aborting navigation")
                return False

            current = self.detect_current()
            logger.info(f"  [step {step_idx}/{max_steps}] current state: {current}")

            if current == target:
                logger.info(f"  arrived at {target!r}")
                return True

            path = self.find_path(current, target)
            if path is None:
                logger.error(f"  no path from {current!r} to {target!r}")
                return False
            if not path:
                # Already at target but the previous detect missed it.
                return True

            next_state, trans = path[0]
            signature = (current, trans.action.type)

            if signature == last_signature:
                stuck_count += 1
                if stuck_count >= self.DEAD_TRANSITION_LIMIT:
                    logger.error(
                        f"  dead transition: {current!r} --{trans.action.type}--> "
                        f"{next_state!r} fired {stuck_count + 1}x without changing "
                        "state. Check the YAML."
                    )
                    return False
            else:
                stuck_count = 0
            last_signature = signature

            logger.info(f"    -> {next_state!r} via action={trans.action.type}")

            ok = self._execute_action(trans)
            if not ok:
                logger.error(f"    action execution failed: {trans.action}")
                return False

            if not self._wait_for_state(next_state, trans.wait_for_change_sec):
                logger.warning(
                    f"    did not arrive at {next_state!r} within "
                    f"{trans.wait_for_change_sec}s — may need a retry"
                )

        logger.error(f"failed to reach {target!r} within {max_steps} steps")
        return False

    # ----- Internal: dispatch an action -----

    def _execute_action(self, trans: Transition) -> bool:
        a = trans.action

        if isinstance(a, TapTextAction):
            return self._execute_tap_text(a)

        if isinstance(a, TapCoordsAction):
            self.ctx.input.tap(a.x, a.y)
            return True

        if isinstance(a, KeyeventAction):
            if a.key == "BACK":
                self.ctx.input.back()
            elif a.key == "HOME":
                self.ctx.input.home()
            return True

        if isinstance(a, SwipeAction):
            self.ctx.input.swipe(a.x1, a.y1, a.x2, a.y2, a.duration_ms)
            return True

        if isinstance(a, WaitUntilAction):
            # No action — _wait_for_state handles the wait afterwards.
            return True

        logger.error(f"unknown action type: {a}")
        return False

    def _execute_tap_text(self, a: TapTextAction) -> bool:
        img = self.ctx.capture.screenshot()
        ocr_fast = self.ctx.state.ocr  # fast engine, already loaded by StateDetector

        # 1. Fast OCR.
        r = ocr_fast.find_text(
            img, a.text, exact=a.exact, min_confidence=a.min_confidence
        )
        if r is not None:
            logger.info(f"      found {a.text!r} @ {r.center} (fast OCR)")
            self.ctx.input.tap(*r.center)
            return True

        # 2. Coord fallback.
        if a.fallback_coords and len(a.fallback_coords) == 2:
            x, y = a.fallback_coords
            logger.info(
                f"      fast OCR missed {a.text!r} — using fallback_coords ({x}, {y})"
            )
            self.ctx.input.tap(x, y)
            return True

        # 3. Accurate OCR (only if the user wired one up).
        if self.ctx.ocr_accurate is not None:
            logger.info(
                f"      fast OCR missed and no fallback_coords — trying accurate OCR for {a.text!r}"
            )
            r = self.ctx.ocr_accurate.find_text(
                img, a.text, exact=a.exact, min_confidence=a.min_confidence
            )
            if r is not None:
                logger.info(f"      found {a.text!r} @ {r.center} (accurate OCR)")
                self.ctx.input.tap(*r.center)
                return True

        logger.warning(
            f"      tap_text could not locate {a.text!r} via any strategy"
        )
        return False

    # ----- Internal: poll for state change -----

    def _wait_for_state(
        self,
        target: str,
        timeout_sec: float,
        poll_interval: float = 1.0,
    ) -> bool:
        start = time.time()
        while time.time() - start < timeout_sec:
            if self._cancelled():
                return False
            if self.detect_current() == target:
                return True
            time.sleep(poll_interval)
        return False

    def _cancelled(self) -> bool:
        ev = self.ctx.cancel_event
        return ev is not None and ev.is_set()
