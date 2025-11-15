import os
import json

import config
import parsing

# Try to import OCR deps
try:
    from PIL import Image
    import pytesseract
    from pytesseract import Output  # noqa: F401

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    Image = None
    print("OCR not available (install pillow + pytesseract).")


def load_ocr_cache_all():
    if not os.path.exists(config.OCR_CACHE_FILE):
        return {}
    try:
        with open(config.OCR_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_ocr_cache_all(cache_all):
    try:
        with open(config.OCR_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_all, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def build_image_ocr_index_for_chat(chat_state):
    """
    Given a ChatState, populate:
      chat_state.image_ocr[filename] = lower-case text
      chat_state.image_boxes[filename] = list of box dicts
    And save to shared OCR cache file.
    """
    if not OCR_AVAILABLE:
        return

    image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp")
    all_cache = load_ocr_cache_all()
    chat_cache = all_cache.get(chat_state.chat_id, {})

    seen = set()

    for msg in chat_state.messages:
        for fname in msg.get("attachments", []):
            fname_clean = parsing.clean_attachment(fname)
            if fname_clean in seen:
                continue
            seen.add(fname_clean)

            if not fname_clean.lower().endswith(image_exts):
                continue

            image_path = os.path.join(chat_state.media_dir, fname_clean)
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
                chat_state.image_ocr[fname_clean] = text.lower()
                chat_state.image_boxes[fname_clean] = boxes
                print(f"[{chat_state.chat_id}] OCR cache hit for {fname_clean}")
                continue

            # fresh OCR
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
                chat_state.image_ocr[fname_clean] = full_text.lower()
                chat_state.image_boxes[fname_clean] = boxes

                chat_cache[fname_clean] = {
                    "text": full_text,
                    "mtime": mtime,
                    "boxes": boxes,
                }
                print(f"[{chat_state.chat_id}] OCR done for {fname_clean}")
            except Exception as e:
                print(f"[{chat_state.chat_id}] OCR failed for {fname_clean}: {e}")
                chat_state.image_ocr[fname_clean] = ""
                chat_state.image_boxes[fname_clean] = []
                chat_cache[fname_clean] = {"text": "", "mtime": mtime, "boxes": []}

    all_cache[chat_state.chat_id] = chat_cache
    save_ocr_cache_all(all_cache)
