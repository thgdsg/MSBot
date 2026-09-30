"""Bounded observations of the bot's own sentence openings."""

import re
from collections import Counter
from datetime import datetime, timezone


WINDOW = 20
FILLER = re.compile(r"^\s*(?:ah|oh|hum|hmm|ora|bom|bem|olha|então)\s*[,!:;—-]\s*", re.I)


def opening(text):
    # Skip quotes, code and lists: their openings need not be the bot's style.
    text = text.strip()
    if not text or text.startswith(('"', "'", '>', '`', '-', '*', '#')):
        return ""
    filler = FILLER.match(text)
    if filler:
        return re.search(r"[^\W\d_]+", filler.group(), re.UNICODE).group().lower() + ","
    words = re.findall(r"[^\W\d_]+", text.lower(), re.UNICODE)
    return " ".join(words[:3]) if len(words) >= 3 else ""


def observe(state, answer):
    recent = state.setdefault("recent", [])
    recent.append(opening(answer))
    del recent[:-WINDOW]
    counts = Counter(value for value in recent if value)
    state["habits"] = [
        {"opening": value, "count": count}
        for value, count in counts.most_common(5)
        if count >= 3 and count / len(recent) >= 0.25
    ]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()


def render(state):
    habits = state.get("habits", [])
    if not habits:
        return ""
    lines = ["", "<!-- WritingStyle -->", "## Manias de escrita do bot",
             "Varie as aberturas; evite os seguintes inicios recorrentes nas proximas respostas:"]
    for habit in habits:
        lines.append(f"- {habit['opening']!r}: {habit['count']} das ultimas {len(state['recent'])} respostas.")
    lines.extend(["Nao transforme estas observacoes em fatos sobre os usuarios.",
                  "<!-- /WritingStyle -->"])
    return "\n".join(lines)


def suppress_filler(answer, state):
    match = FILLER.match(answer)
    if match and any(item['opening'] == opening(answer) for item in state.get('habits', [])):
        remainder = answer[match.end():].strip()
        if remainder:
            return remainder
    return answer
