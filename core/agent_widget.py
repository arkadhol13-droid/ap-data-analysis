
import time

import streamlit as st

_STYLE = """
<style>
  .neon-wrap{
    display:flex; align-items:center; gap:18px;
    background:#07050d; border:1px solid #241a3a; border-radius:16px;
    padding:16px 22px; margin: 6px 0 14px 0;
  }
  .neon-wrap svg{ width:64px; height:72px; flex-shrink:0; overflow:visible; }
  .neon-text{ font-family:'Space Grotesk', sans-serif; }
  .neon-phase{ font-size:0.7rem; letter-spacing:0.18em; text-transform:uppercase; color:#c084fc; opacity:0.9; }
  .neon-msg{ font-size:0.95rem; color:#ece9f7; margin-top:2px; }

  .n-body{ fill:url(#neonBodyGrad); }
  .n-eye{ fill:#c084fc; }
  .n-eye-glow{ fill:#c084fc; opacity:0.35; }
  .n-ring{ stroke:#7c3aed; stroke-width:1; fill:none; opacity:0.5; }

  @keyframes n-bob{ 0%,100%{ transform:translateY(0);} 50%{ transform:translateY(-3px);} }
  @keyframes n-blink{ 0%,88%,100%{ transform:scaleY(1);} 92%{ transform:scaleY(0.15);} }
  @keyframes n-scan{ 0%,100%{ transform:translateX(-2px);} 50%{ transform:translateX(2px);} }
  @keyframes n-ringspin{ from{ transform:rotate(0deg);} to{ transform:rotate(360deg);} }
  @keyframes n-flicker{ 0%,100%{ opacity:0.9;} 50%{ opacity:0.5;} }
  @keyframes n-pop{ 0%{ transform:scale(0.4); opacity:0;} 60%{ transform:scale(1.15); opacity:1;} 100%{ transform:scale(1); opacity:1;} }
  @keyframes n-pulse-red{ 0%,100%{ fill:#c084fc;} 50%{ fill:#f87171;} }
  @keyframes n-glowpulse{ 0%,100%{ opacity:0.3;} 50%{ opacity:0.8;} }

  .neon-idle .n-char{ animation:n-bob 3.2s ease-in-out infinite; transform-origin:center; }
  .neon-idle .n-eye-l, .neon-idle .n-eye-r{ animation:n-blink 4.5s infinite; transform-origin:center; }

  .neon-scanning .n-char{ animation:n-bob 3.2s ease-in-out infinite; transform-origin:center; }
  .neon-scanning .n-eyes{ animation:n-scan 0.7s ease-in-out infinite; }
  .neon-scanning .n-ring{ animation:n-ringspin 1.4s linear infinite; transform-origin:32px 40px; }

  .neon-analyzing .n-char{ animation:n-bob 2.2s ease-in-out infinite; transform-origin:center; }
  .neon-analyzing .n-ring{ animation:n-ringspin 0.9s linear infinite; transform-origin:32px 40px; }
  .neon-analyzing .n-chip{ animation:n-flicker 0.6s ease-in-out infinite; }

  .neon-discovery .n-mark{ animation:n-pop 0.4s ease-out 1; }
  .neon-discovery .n-eye{ animation:n-flicker 0.35s ease-in-out 3; }

  .neon-insight .n-panel{ animation:n-pop 0.5s ease-out 1; }
  .neon-insight .n-glow{ animation:n-glowpulse 1.6s ease-in-out infinite; }

  .neon-warning .n-eye{ animation:n-pulse-red 0.7s ease-in-out infinite; }
  .neon-warning .n-warn-glow{ animation:n-glowpulse 0.8s ease-in-out infinite; }
</style>
"""

_PHASES = [
    ("idle", "⚡ Task received", "Neon is picking up your question..."),
    ("scanning", "🔎 Scanning", "Looking deep into your data..."),
    ("analyzing", "🧠 Analyzing", "Connecting the unconnected..."),
    ("discovery", "❗ Discovery", "Found something interesting!"),
    ("insight", "✨ Insight", "Here's what I found."),
]


def _character_body(state: str) -> str:
    """The shared ghost silhouette: round glossy head tapering into a
    three-point wavy hem, standing on a soft glow ring -- reused across
    every state, only the accents (eyes, rings, icons) change."""
    return """
    <g class="n-char">
      <ellipse class="n-glow" cx="32" cy="66" rx="20" ry="4" fill="#7c3aed" opacity="0.35"/>
      <path class="n-body"
        d="M 12 40
           Q 8 8 32 6
           Q 56 8 52 40
           L 54 58
           Q 44 50 38 60
           Q 32 48 26 60
           Q 20 50 10 58
           Z"
      />
      <g class="n-eyes">
        <ellipse class="n-eye n-eye-l" cx="24" cy="34" rx="4.2" ry="6"/>
        <ellipse class="n-eye n-eye-r" cx="40" cy="34" rx="4.2" ry="6"/>
      </g>
    </g>
    """


def _state_accents(state: str) -> str:
    if state == "scanning":
        return """
        <circle class="n-ring" cx="32" cy="40" r="26"/>
        <circle class="n-ring" cx="32" cy="40" r="20" opacity="0.3"/>
        """
    if state == "analyzing":
        return """
        <circle class="n-ring" cx="32" cy="40" r="24"/>
        <rect class="n-chip" x="46" y="46" width="10" height="8" rx="1.5" fill="#38bdf8" opacity="0.85"/>
        """
    if state == "discovery":
        return """
        <g class="n-mark" style="transform-origin:48px 12px;">
          <text x="46" y="18" font-size="16" fill="#facc15" font-weight="bold">!</text>
        </g>
        """
    if state == "insight":
        return """
        <g class="n-panel" style="transform-origin:50px 30px;">
          <rect x="44" y="14" width="16" height="20" rx="2" fill="#0b0e17" stroke="#7c3aed" stroke-width="1"/>
          <rect x="47" y="26" width="2.5" height="6" fill="#38bdf8"/>
          <rect x="51" y="22" width="2.5" height="10" fill="#c084fc"/>
          <rect x="55" y="18" width="2.5" height="14" fill="#38bdf8"/>
        </g>
        """
    if state == "warning":
        return """
        <ellipse class="n-warn-glow" cx="32" cy="40" rx="30" ry="34" fill="#f87171" opacity="0.12"/>
        <path d="M 48 10 L 56 24 L 40 24 Z" fill="none" stroke="#f87171" stroke-width="1.6"/>
        <text x="46.5" y="21" font-size="8" fill="#f87171" font-weight="bold">!</text>
        """
    return ""  # idle -- no extra accents


def _frame_html(state: str, phase_label: str, message: str) -> str:
    return f"""
    {_STYLE}
    <div class="neon-wrap">
        <svg viewBox="0 0 64 72" class="neon-{state}">
            <defs>
                <linearGradient id="neonBodyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#1a1230"/>
                    <stop offset="100%" stop-color="#050308"/>
                </linearGradient>
            </defs>
            {_character_body(state)}
            {_state_accents(state)}
        </svg>
        <div class="neon-text">
            <div class="neon-phase">{phase_label}</div>
            <div class="neon-msg">{message}</div>
        </div>
    </div>
    """


def render_state(placeholder, state: str, phase_label: str, message: str):
    """Renders a single named state (idle/scanning/analyzing/discovery/
    insight/warning) into the given st.empty() placeholder. Use this
    directly (e.g. `warning` for a rate-limit message) outside the fixed
    sequence below."""
    placeholder.html(_frame_html(state, phase_label, message))


def run_agent_sequence(placeholder, step_seconds: float = 0.45):
    """
    Plays Task Received -> Scanning -> Analyzing -> Discovery -> Insight
    into the given placeholder, then leaves the final frame showing
    before the caller replaces it with the real answer. Kept short
    (~2s total) by design -- premium and quick, not a long loading loop.
    """
    for state, label, message in _PHASES:
        render_state(placeholder, state, label, message)
        time.sleep(step_seconds)
