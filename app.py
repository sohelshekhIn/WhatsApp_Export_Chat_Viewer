from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    abort,
    jsonify,
)
from datetime import datetime
import os
import re
import html
import json
import sqlite3

# ---------- CONFIG ----------
CHAT_ROOT = "."  
OCR_CACHE_FILE = "image_ocr_cache_multi.json"
DB_PATH = "image_meta.db"
SELF_NAME = "Sohel Shekh"  # your own name as appears in WhatsApp export

app = Flask(__name__)

# ---------- OCR SETUP ----------
try:
    from PIL import Image
    import pytesseract
    from pytesseract import Output  # noqa: F401

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("OCR not available (install pillow + pytesseract).")

# ---------- SQLITE SETUP ----------
DB = sqlite3.connect(DB_PATH, check_same_thread=False)
DB.row_factory = sqlite3.Row
DB.execute(
    """
CREATE TABLE IF NOT EXISTS image_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE,
    record_found INTEGER DEFAULT 0,
    recorded INTEGER DEFAULT 0,
    not_found INTEGER DEFAULT 0,
    payment_record INTEGER DEFAULT 0,
    note TEXT DEFAULT ''
)
"""
)
DB.commit()

# ---------- WHATSAPP INVISIBLE CHARS ----------
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


# ---------- OCR CACHE ----------
def load_ocr_cache_all():
    if not os.path.exists(OCR_CACHE_FILE):
        return {}
    try:
        with open(OCR_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_ocr_cache_all(cache_all):
    try:
        with open(OCR_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_all, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------- PER-CHAT STATE ----------
class ChatState:
    def __init__(self, chat_id: str, base_dir: str):
        self.chat_id = chat_id
        self.base_dir = base_dir
        self.chat_file = os.path.join(base_dir, "_chat.txt")
        self.media_dir = os.path.join(base_dir, "Media")
        self.messages = []
        self.image_ocr = {}  # filename -> text lower
        self.image_boxes = {}  # filename -> boxes

    def load(self):
        if not os.path.exists(self.chat_file):
            print(f"[{self.chat_id}] _chat.txt not found at {self.chat_file}")
            return
        self.messages = parse_chat(self.chat_file)
        print(f"[{self.chat_id}] Loaded {len(self.messages)} messages.")
        if os.path.isdir(self.media_dir) and OCR_AVAILABLE:
            build_image_ocr_index_for_chat(self)
        else:
            print(f"[{self.chat_id}] Media dir missing or OCR disabled; skip OCR.")


CHATS = {}  # chat_id -> ChatState


def discover_chats():
    chats = []
    for name in sorted(os.listdir(CHAT_ROOT)):
        path = os.path.join(CHAT_ROOT, name)
        if not os.path.isdir(path):
            continue
        if os.path.exists(os.path.join(path, "_chat.txt")) and os.path.isdir(
            os.path.join(path, "Media")
        ):
            chats.append({"id": name, "path": path})
    return chats


def get_chat_state(chat_id: str):
    if not chat_id:
        return None
    if chat_id in CHATS:
        return CHATS[chat_id]
    base_dir = os.path.join(CHAT_ROOT, chat_id)
    if not os.path.isdir(base_dir):
        return None
    chat = ChatState(chat_id, base_dir)
    chat.load()
    CHATS[chat_id] = chat
    return chat


def build_image_ocr_index_for_chat(chat: ChatState):
    if not OCR_AVAILABLE:
        return

    image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp")
    all_cache = load_ocr_cache_all()
    chat_cache = all_cache.get(chat.chat_id, {})

    seen = set()

    for msg in chat.messages:
        for fname in msg.get("attachments", []):
            fname_clean = clean_attachment(fname)
            if fname_clean in seen:
                continue
            seen.add(fname_clean)

            if not fname_clean.lower().endswith(image_exts):
                continue

            image_path = os.path.join(chat.media_dir, fname_clean)
            if not os.path.exists(image_path):
                continue

            try:
                mtime = os.path.getmtime(image_path)
            except OSError:
                mtime = None

            cached = chat_cache.get(fname_clean)
            if (
                cached
                and isinstance(cached, dict)
                and cached.get("mtime") == mtime
                and "text" in cached
            ):
                text = cached.get("text") or ""
                boxes = cached.get("boxes") or []
                chat.image_ocr[fname_clean] = text.lower()
                chat.image_boxes[fname_clean] = boxes
                print(f"[{chat.chat_id}] OCR cache hit for {fname_clean}")
                continue

            try:
                img = Image.open(image_path)
                data = pytesseract.image_to_data(
                    img, lang="eng", output_type=Output.DICT
                )

                full_text_parts = []
                boxes = []
                n = len(data["text"])
                for i in range(n):
                    word = data["text"][i]
                    if not word or word.strip() == "":
                        continue
                    w_norm = word.strip()
                    full_text_parts.append(w_norm)
                    box = {
                        "text": w_norm.lower(),
                        "left": int(data["left"][i]),
                        "top": int(data["top"][i]),
                        "width": int(data["width"][i]),
                        "height": int(data["height"][i]),
                    }
                    boxes.append(box)

                full_text = " ".join(full_text_parts)
                chat.image_ocr[fname_clean] = full_text.lower()
                chat.image_boxes[fname_clean] = boxes
                chat_cache[fname_clean] = {
                    "text": full_text,
                    "mtime": mtime,
                    "boxes": boxes,
                }
                print(f"[{chat.chat_id}] OCR done for {fname_clean}")
            except Exception as e:
                print(f"[{chat.chat_id}] OCR failed for {fname_clean}: {e}")
                chat.image_ocr[fname_clean] = ""
                chat.image_boxes[fname_clean] = []
                chat_cache[fname_clean] = {"text": "", "mtime": mtime, "boxes": []}

    all_cache[chat.chat_id] = chat_cache
    save_ocr_cache_all(all_cache)


# ---------- IMAGE META HELPERS (PER CHAT) ----------
def meta_key(chat_id: str, filename: str) -> str:
    filename = clean_attachment(filename)
    return f"{chat_id}::{filename}"


def get_image_meta(chat_id: str, filename: str):
    key = meta_key(chat_id, filename)
    cur = DB.execute(
        "SELECT record_found, recorded, not_found, payment_record, note "
        "FROM image_meta WHERE filename = ?",
        (key,),
    )
    row = cur.fetchone()
    if not row:
        return {
            "record_found": 0,
            "recorded": 0,
            "not_found": 0,
            "payment_record": 0,
            "note": "",
        }
    return {
        "record_found": int(row["record_found"]),
        "recorded": int(row["recorded"]),
        "not_found": int(row["not_found"]),
        "payment_record": int(row["payment_record"]),
        "note": row["note"] or "",
    }


def save_image_meta(
    chat_id: str,
    filename: str,
    record_found: int,
    recorded: int,
    not_found: int,
    payment_record: int,
    note: str,
):
    key = meta_key(chat_id, filename)
    DB.execute(
        """
        INSERT INTO image_meta (filename, record_found, recorded, not_found, payment_record, note)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(filename) DO UPDATE SET
            record_found = excluded.record_found,
            recorded = excluded.recorded,
            not_found = excluded.not_found,
            payment_record = excluded.payment_record,
            note = excluded.note
        """,
        (key, record_found, recorded, not_found, payment_record, note),
    )
    DB.commit()


# ---------- ROUTES ----------
@app.route("/media/<chat_id>/<path:filename>")
def media(chat_id, filename):
    chat = get_chat_state(chat_id)
    if not chat or not os.path.isdir(chat.media_dir):
        abort(404)
    filename = clean_attachment(filename)
    full_path = os.path.join(chat.media_dir, filename)
    if not os.path.exists(full_path):
        abort(404)
    return send_from_directory(chat.media_dir, filename)


@app.route("/image_meta/<chat_id>/<path:filename>", methods=["GET", "POST"])
def image_meta_route(chat_id, filename):
    chat = get_chat_state(chat_id)
    if not chat:
        abort(404)
    fname = clean_attachment(filename)

    if request.method == "GET":
        meta = get_image_meta(chat_id, fname)
        return jsonify({"filename": fname, **meta})

    data = request.get_json(force=True) or {}
    rf = 1 if data.get("record_found") else 0
    rec = 1 if data.get("recorded") else 0
    nf = 1 if data.get("not_found") else 0
    pay = 1 if data.get("payment_record") else 0
    note = data.get("note") or ""
    save_image_meta(chat_id, fname, rf, rec, nf, pay, note)
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    chat_id = (request.args.get("chat") or "").strip()

    # No chat selected -> show picker
    if not chat_id:
        chats = discover_chats()
        return render_template("picker.html", chats=chats)

    chat = get_chat_state(chat_id)
    if not chat or not chat.messages:
        return f"Chat '{chat_id}' not found or _chat.txt is empty.", 404

    messages = chat.messages
    image_ocr = chat.image_ocr
    image_boxes = chat.image_boxes
    media_dir = chat.media_dir

    q_raw = (request.args.get("q") or "").strip()
    q = q_raw.lower()

    search_notes_flag = request.args.get("search_notes", "1")
    search_notes = search_notes_flag == "1"

    # date filters
    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    start_date = None
    end_date = None
    if start_str:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = None
    if end_str:
        try:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = None

    # status filters
    status_keys = ["record_found", "recorded", "not_found", "payment_record"]
    include_filters = {k: bool(request.args.get(f"inc_{k}")) for k in status_keys}
    exclude_filters = {k: bool(request.args.get(f"exc_{k}")) for k in status_keys}

    # collect filenames
    all_filenames = set()
    for msg in messages:
        for fname in msg.get("attachments", []):
            all_filenames.add(fname)

    # meta + note html
    image_meta_map = {}
    image_note_html = {}

    def highlight_text(text: str) -> str:
        if not text:
            return ""
        base = html.escape(text)
        if not q_raw:
            return base
        pattern = re.compile(re.escape(q_raw), re.IGNORECASE)

        def _repl(m):
            return f'<span class="hl">{m.group(0)}</span>'

        return pattern.sub(_repl, base)

    for fname in all_filenames:
        meta = get_image_meta(chat_id, fname)
        image_meta_map[fname] = meta
        note = meta.get("note") or ""
        if not note:
            image_note_html[fname] = ""
        else:
            if q and search_notes:
                image_note_html[fname] = highlight_text(note)
            else:
                image_note_html[fname] = html.escape(note)

    filtered = []
    match_count = 0
    image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp")

    for msg in messages:
        dt = msg["datetime"]
        msg_date = dt.date() if dt else None

        if start_date and msg_date and msg_date < start_date:
            continue
        if end_date and msg_date and msg_date > end_date:
            continue

        img_text_blob = ""
        attachment_ocr = {}
        attachment_boxes = {}
        msg_note_blob = ""

        for fname in msg.get("attachments", []):
            key = clean_attachment(fname)
            lower = key.lower()

            # OCR only for images
            ocr_txt = ""
            if lower.endswith(image_exts):
                ocr_txt = image_ocr.get(key, "")
                img_text_blob += " " + (ocr_txt or "")
            if ocr_txt:
                attachment_ocr[fname] = (
                    highlight_text(ocr_txt) if q else html.escape(ocr_txt)
                )
            else:
                attachment_ocr[fname] = ""

            # bounding boxes (normalized) only for images and if searching
            boxes = []
            if q and lower.endswith(image_exts):
                raw_boxes = image_boxes.get(key, [])
                image_path = os.path.join(media_dir, key)
                img_w = img_h = None
                try:
                    with Image.open(image_path) as im:
                        img_w, img_h = im.size
                except Exception:
                    img_w = img_h = None

                if img_w and img_h:
                    for b in raw_boxes:
                        word_text = b.get("text", "")
                        if q in word_text:
                            x = b["left"] / img_w
                            y = b["top"] / img_h
                            w = b["width"] / img_w
                            h = b["height"] / img_h
                            boxes.append({"x": x, "y": y, "w": w, "h": h})
            attachment_boxes[fname] = boxes

            meta = image_meta_map.get(fname, {"note": ""})
            note = (meta.get("note") or "").lower()
            msg_note_blob += " " + note

        base_match = False
        ocr_match = False
        has_match = False

        if q:
            combo = f"{msg['sender']} {msg['text']}".lower()
            if search_notes:
                combo += msg_note_blob
            base_match = q in combo
            ocr_match = q in img_text_blob if img_text_blob else False
            has_match = base_match or ocr_match
            if has_match:
                match_count += 1
        else:
            has_match = False

        new_msg = dict(msg)
        new_msg["display_text"] = highlight_text(msg["text"])
        new_msg["image_match"] = ocr_match
        new_msg["has_match"] = has_match
        new_msg["attachment_ocr"] = attachment_ocr
        new_msg["attachment_boxes"] = attachment_boxes
        filtered.append(new_msg)

    # side-panel filtered images (only image files)
    filtered_images_map = {}
    for idx, msg in enumerate(filtered):
        for fname in msg.get("attachments", []):
            lower = fname.lower()
            if not lower.endswith(image_exts):
                continue
            if fname in filtered_images_map:
                continue
            meta = image_meta_map.get(
                fname,
                {
                    "record_found": 0,
                    "recorded": 0,
                    "not_found": 0,
                    "payment_record": 0,
                    "note": "",
                },
            )

            # include filters
            include_ok = True
            if any(include_filters.values()):
                for k, inc in include_filters.items():
                    if inc and not meta.get(k, 0):
                        include_ok = False
                        break
            if not include_ok:
                continue

            # exclude filters
            exclude_fail = False
            for k, ex in exclude_filters.items():
                if ex and meta.get(k, 0):
                    exclude_fail = True
                    break
            if exclude_fail:
                continue

            filtered_images_map[fname] = {
                "filename": fname,
                "meta": meta,
                "msg_idx": idx,
            }

    filtered_images = list(filtered_images_map.values())

    return render_template(
        "chat.html",
        filtered=filtered,
        total=len(messages),
        self_name=SELF_NAME,
        match_count=match_count,
        image_meta_map=image_meta_map,
        image_note_html=image_note_html,
        filtered_images=filtered_images,
        chat_id=chat_id,
    )


if __name__ == "__main__":
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True)
