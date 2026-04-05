from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FONT_PATH = Path(r"C:\Windows\Fonts\consola.ttf")
FONT_BOLD_PATH = Path(r"C:\Windows\Fonts\consolab.ttf")

WIDTH = 1500
HEIGHT = 900
PADDING_X = 42
PADDING_Y = 34
LINE_GAP = 8
TITLEBAR_HEIGHT = 54
STATUSLINE_HEIGHT = 30
FONT_SIZE = 24
SMALL_SIZE = 18

BG = "#0a0f14"
PANEL = "#0f1722"
TITLEBAR = "#111827"
BORDER = "#223041"
TEXT = "#d7e2f0"
MUTED = "#8da2b8"
ACCENT = "#66d9ef"
SUCCESS = "#96f2a2"
ERROR = "#ff7b72"
PROMPT = "#7dd3fc"
CODE = "#facc15"


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


FONT = load_font(FONT_PATH, FONT_SIZE)
FONT_BOLD = load_font(FONT_BOLD_PATH, FONT_SIZE)
SMALL = load_font(FONT_PATH, SMALL_SIZE)


def line_color(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("[hint]") or stripped.startswith("[fallback]") or stripped.startswith("[cancelled]"):
        return ERROR
    if stripped.startswith("[thinking]") or stripped.startswith("[step") or stripped.startswith("[wait]"):
        return MUTED
    if stripped.startswith("[goal]") or stripped.startswith("[plan]") or stripped.startswith("[tool]"):
        return ACCENT
    if stripped.startswith("[answer]") or stripped.startswith("Answer:") or stripped.startswith("Reasoning summary:"):
        return SUCCESS
    if stripped.startswith("[") and "] >" in stripped:
        return PROMPT
    if stripped.startswith("/") or stripped.startswith("personal-agent-toolkit") or stripped.startswith("python -m"):
        return CODE
    return TEXT


def wrap_terminal_line(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    if draw.textlength(text, font=font) <= max_width:
        return [text]
    words = text.split(" ")
    if len(words) == 1:
        chunks: list[str] = []
        current = ""
        for char in text:
            candidate = current + char
            if current and draw.textlength(candidate, font=font) > max_width:
                chunks.append(current)
                current = char
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    wrapped: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if current and draw.textlength(candidate, font=font) > max_width:
            wrapped.append(current)
            current = word
        else:
            current = candidate
    if current:
        wrapped.append(current)
    return wrapped


def draw_terminal(lines: list[str], *, footer: str | None = None) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((16, 16, WIDTH - 16, HEIGHT - 16), radius=18, fill=PANEL, outline=BORDER, width=2)
    draw.rounded_rectangle((16, 16, WIDTH - 16, 16 + TITLEBAR_HEIGHT), radius=18, fill=TITLEBAR, outline=BORDER, width=2)
    draw.rectangle((16, 16 + TITLEBAR_HEIGHT - 18, WIDTH - 16, 16 + TITLEBAR_HEIGHT), fill=TITLEBAR)

    for index, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        cx = 40 + index * 24
        cy = 43
        draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=color)

    draw.text((100, 28), "personal-agent-toolkit", font=SMALL, fill=MUTED)

    y = 16 + TITLEBAR_HEIGHT + PADDING_Y
    max_width = WIDTH - 2 * PADDING_X
    max_y = HEIGHT - 110 if footer else HEIGHT - 40
    for raw_line in lines:
        font = FONT_BOLD if raw_line.startswith("Personal Agent Toolkit") else FONT
        for wrapped in wrap_terminal_line(draw, raw_line, font, max_width):
            if y > max_y:
                break
            draw.text((PADDING_X, y), wrapped, font=font, fill=line_color(raw_line))
            y += FONT_SIZE + LINE_GAP

    if footer:
        draw.rounded_rectangle(
            (PADDING_X, HEIGHT - 78, WIDTH - PADDING_X, HEIGHT - 32),
            radius=12,
            fill=TITLEBAR,
            outline=BORDER,
            width=1,
        )
        draw.text((PADDING_X + 18, HEIGHT - 66), footer, font=SMALL, fill=MUTED)

    return image


def build_typing_frames(base_lines: list[str], prompt_line: str, output_lines: list[str], footer: str, *, final_hold: int = 4) -> list[Image.Image]:
    frames: list[Image.Image] = []
    for stop in (max(1, len(prompt_line) // 3), max(1, 2 * len(prompt_line) // 3), len(prompt_line)):
        frames.append(draw_terminal(base_lines + [prompt_line[:stop]], footer=footer))
    staged = list(base_lines) + [prompt_line]
    for count in range(1, len(output_lines) + 1):
        frames.append(draw_terminal(staged + output_lines[:count], footer=footer))
    if frames:
        frames.extend([frames[-1]] * final_hold)
    return frames


def save_gif(name: str, frames: list[Image.Image], *, duration: int = 380) -> None:
    if not frames:
        raise ValueError("no frames")
    out_path = DOCS / f"{name}.gif"
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        optimize=False,
        duration=duration,
        loop=0,
    )
    frames[-1].save(DOCS / f"{name}.png")


STARTUP_BASE = [
    "Personal Agent Toolkit",
    "========================",
    "Session : planner | ollama | qwen2.5-coder:14b",
    "Workspace : personal-agent-toolkit",
    "Reasoning : public summaries on",
    "",
    "Try this first:",
    "  /help    command guide",
    "  /status  session snapshot",
    "  /clear   clean terminal view",
    "  /agents  switch persona/profile",
    "  /skills  inspect available skills",
    "  /plan    review the current plan",
    "",
    "Enter a prompt or slash command. Use /quit to exit.",
    "ollama | qwen2.5-coder:14b | planner | reasoning=public | stream=on | timeout=300 | tasks=0 | plan=0 | ws=personal-agent-toolkit",
]

STARTUP_PROMPT = "[planner|qwen2.5-coder...+r] > /status"
STARTUP_OUTPUT = [
    "Session status",
    "provider: ollama",
    "model: qwen2.5-coder:14b",
    "agent: planner",
    "reasoning: public",
    "stream: on",
    "timeout: 300.0",
    "workspace: D:\\JavascriptProjects\\claudcode\\personal-agent-toolkit",
    "config: (none)",
    "skills: (none)",
    "tasks: 0",
    "plan: (untitled) (0 steps)",
]

WORKFLOW_BASE = [
    "Personal Agent Toolkit",
    "========================",
    "Session : planner | ollama | qwen2.5-coder:14b",
    "Workspace : personal-agent-toolkit",
    "Reasoning : public summaries on",
    "",
    "ollama | qwen2.5-coder:14b | planner | reasoning=public | stream=on | timeout=300 | tasks=0 | plan=2 | ws=personal-agent-toolkit",
]

WORKFLOW_PROMPT = "[planner|qwen2.5-coder...+r] > /workflow capture-note interview-prep"
WORKFLOW_OUTPUT = [
    "Captured workflow note for: interview-prep",
    "",
    "memory_saved:n4x7bc2a",
    "ollama | qwen2.5-coder:14b | planner | reasoning=public | stream=on | timeout=300 | tasks=0 | plan=2 | ws=personal-agent-toolkit",
    "[planner|qwen2.5-coder...+r] > /memory-search interview",
    "n4x7bc2a: workflow:interview-prep",
]

EDITING_BASE = [
    "Personal Agent Toolkit",
    "========================",
    "Session : coder | ollama | qwen2.5-coder:14b",
    "Workspace : personal-agent-toolkit",
    "Reasoning : standard",
    "",
    "ollama | qwen2.5-coder:14b | coder | reasoning=std | stream=on | timeout=300 | tasks=0 | plan=0 | ws=personal-agent-toolkit",
]

EDITING_PROMPT = "[coder|qwen2.5-coder:14b] > /grep personal_agent_toolkit ."
EDITING_OUTPUT = [
    "README.md:73: python -m personal_agent_toolkit --prompt \"/help\"",
    "README.md:131: python -m personal_agent_toolkit --provider ollama --local-profile balanced",
    "personal_agent_toolkit\\__main__.py:414: def create_engine(",
    "personal_agent_toolkit\\core\\builtin_commands.py:1117: Command(name=\"doctor\", description=\"Run actionable diagnostics and setup checks\", handler=doctor_command)",
]


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    save_gif(
        "demo-startup",
        build_typing_frames(
            STARTUP_BASE,
            STARTUP_PROMPT,
            STARTUP_OUTPUT,
            footer="Demo: startup HUD, prompt context, and /status",
        ),
    )
    save_gif(
        "demo-workflow-memory",
        build_typing_frames(
            WORKFLOW_BASE,
            WORKFLOW_PROMPT,
            WORKFLOW_OUTPUT,
            footer="Demo: workflow execution and persistent memory",
        ),
    )
    save_gif(
        "demo-editing",
        build_typing_frames(
            EDITING_BASE,
            EDITING_PROMPT,
            EDITING_OUTPUT,
            footer="Demo: repo search and editing-oriented CLI flow",
        ),
    )


if __name__ == "__main__":
    main()
