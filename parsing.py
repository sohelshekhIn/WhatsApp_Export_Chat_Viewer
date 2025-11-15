from datetime import datetime
import re

# WhatsApp special/invisible characters
WHATSAPP_INVISIBLE = [
    "\u200e",  # LRM
    "\u200f",  # RLM
    "\u202a",  # LRE
    "\u202b",  # RLE
    "\u202c",  # PDF
    "\u202d",  # LRO
    "\u202e",  # RLO
    "\u2066",  # LRI
    "\u2067",  # RLI
    "\u2068",  # FSI
    "\u2069",  # PDI
]


def strip_whatsapp_invisible(s: str) -> str:
    if not s:
        return s
    return "".join(ch for ch in s if ch not in WHATSAPP_INVISIBLE)


def parse_datetime(dt_str: str):
    """Parse WhatsApp-style datetime like '2025-11-12, 8:41:48 PM'."""
    dt_str = dt_str.replace("\u202f", " ")  # narrow no-break space
    dt_str = strip_whatsapp_invisible(dt_str)
    dt_str = " ".join(dt_str.split())

    fmts = [
        "%Y-%m-%d, %I:%M:%S %p",
        "%Y/%m/%d, %I:%M:%S %p",
        "%d/%m/%Y, %I:%M:%S %p",
        "%m/%d/%Y, %I:%M:%S %p",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def clean_sender(name: str) -> str:
    return strip_whatsapp_invisible(name).strip()


def clean_attachment(filename: str) -> str:
    return strip_whatsapp_invisible(filename).strip()


def parse_chat(path: str):
    """
    Parse WhatsApp exported txt into a list of messages:
    [
      {
        "datetime": datetime|None,
        "sender": str,
        "text": str,
        "attachments": [filename, ...]
      }, ...
    ]
    """
    messages = []
    current = None

    attach_re = re.compile(r"<attached:\s*([^>]+)>", re.IGNORECASE)

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = strip_whatsapp_invisible(raw_line.rstrip("\n"))
            if not line.strip():
                continue

            is_new_message = False

            if line.startswith("[") and "]" in line and ":" in line:
                try:
                    closing = line.index("]")
                    dt_str = line[1:closing]
                    rest = line[closing + 2 :]
                    if ": " in rest:
                        sender, text = rest.split(": ", 1)
                    else:
                        sender, text = "Unknown", rest

                    dt = parse_datetime(dt_str)
                    if dt is not None:
                        is_new_message = True
                except Exception:
                    is_new_message = False

            if is_new_message:
                if current:
                    messages.append(current)

                sender = clean_sender(sender)
                text = strip_whatsapp_invisible(text)

                raw_attachments = attach_re.findall(text)
                attachments = [clean_attachment(a) for a in raw_attachments]
                clean_text = attach_re.sub("", text).strip()

                current = {
                    "datetime": dt,
                    "sender": sender,
                    "text": clean_text,
                    "attachments": attachments,
                }
            else:
                # continuation line
                if current:
                    current["text"] += "\n" + line
                else:
                    current = {
                        "datetime": None,
                        "sender": "System",
                        "text": line,
                        "attachments": [],
                    }

    if current:
        messages.append(current)

    return messages
