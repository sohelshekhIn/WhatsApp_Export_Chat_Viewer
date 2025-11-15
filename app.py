# app.py

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

# Pillow only needed here to compute image size for relative OCR boxes
try:
    from PIL import Image
except ImportError:
    Image = None

import config
import parsing
import chat_state
import meta_db

app = Flask(__name__)


@app.route("/media/<chat_id>/<path:filename>")
def media(chat_id, filename):
    chat = chat_state.get_chat_state(chat_id)
    if not chat or not os.path.isdir(chat.media_dir):
        abort(404)
    filename = parsing.clean_attachment(filename)
    full_path = os.path.join(chat.media_dir, filename)
    if not os.path.exists(full_path):
        abort(404)
    return send_from_directory(chat.media_dir, filename)


@app.route("/image_meta/<chat_id>/<path:filename>", methods=["GET", "POST"])
def image_meta_route(chat_id, filename):
    chat = chat_state.get_chat_state(chat_id)
    if not chat:
        abort(404)
    fname = parsing.clean_attachment(filename)

    if request.method == "GET":
        meta = meta_db.get_image_meta(chat_id, fname)
        return jsonify({"filename": fname, **meta})

    data = request.get_json(force=True) or {}
    rf = 1 if data.get("record_found") else 0
    rec = 1 if data.get("recorded") else 0
    nf = 1 if data.get("not_found") else 0
    pay = 1 if data.get("payment_record") else 0
    note = data.get("note") or ""
    meta_db.save_image_meta(chat_id, fname, rf, rec, nf, pay, note)
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    chat_id = (request.args.get("chat") or "").strip()

    # If no chat selected, show picker
    if not chat_id:
        chats = chat_state.discover_chats()
        return render_template("picker.html", chats=chats)

    chat = chat_state.get_chat_state(chat_id)
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

    # load meta for all files
    for fname in all_filenames:
        meta = meta_db.get_image_meta(chat_id, fname)
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

        # date filter
        if start_date and msg_date and msg_date < start_date:
            continue
        if end_date and msg_date and msg_date > end_date:
            continue

        img_text_blob = ""
        attachment_ocr = {}
        attachment_boxes = {}
        msg_note_blob = ""

        for fname in msg.get("attachments", []):
            key = parsing.clean_attachment(fname)
            lower = key.lower()

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

            # bounding boxes (normalized) when searching
            boxes = []
            if q and lower.endswith(image_exts) and Image is not None:
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

    # side-panel filtered images
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
        self_name=config.SELF_NAME,
        match_count=match_count,
        image_meta_map=image_meta_map,
        image_note_html=image_note_html,
        filtered_images=filtered_images,
        chat_id=chat_id,
    )


if __name__ == "__main__":
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=True)
