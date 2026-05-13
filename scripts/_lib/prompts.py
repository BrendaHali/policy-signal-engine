"""
Prompt loader.

Each prompt file in `prompts/<name>.md` contains the production system and
user-template strings inside fenced code blocks tagged `system` and `user`.
Python loads them at runtime so the markdown files are the single source of
truth. The surrounding markdown (model choice, cost notes, design rationale)
is human documentation only.

Example prompt file:

    # Bill classifier

    Some prose for human reviewers.

    ```system
    You are a policy analyst classifying state legislation...
    ```

    ```user
    Bill: {identifier} - {title}
    State: {state}
    ...
    ```
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PROMPTS = ROOT / "prompts"


@lru_cache(maxsize=16)
def load(name: str) -> tuple[str, str]:
    """Return (system, user_template) for the named prompt."""
    path = PROMPTS / f"{name}.md"
    text = path.read_text()
    system = _extract_block(text, "system", path)
    user = _extract_block(text, "user", path)
    return system, user


def _extract_block(text: str, lang: str, path: Path) -> str:
    pattern = rf"```{lang}\n(.*?)\n```"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        raise ValueError(f"prompt file {path} missing a ```{lang} ... ``` block")
    return m.group(1).strip()
