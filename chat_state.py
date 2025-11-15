import os

import config
import parsing
import ocr_utils


class ChatState:
    def __init__(self, chat_id: str, base_dir: str):
        self.chat_id = chat_id
        self.base_dir = base_dir
        self.chat_file = os.path.join(base_dir, "_chat.txt")
        self.media_dir = os.path.join(base_dir, "Media")
        self.messages = []
        self.image_ocr = {}   # filename -> text lower
        self.image_boxes = {} # filename -> boxes

    def load(self):
        if not os.path.exists(self.chat_file):
            print(f"[{self.chat_id}] _chat.txt not found at {self.chat_file}")
            return
        self.messages = parsing.parse_chat(self.chat_file)
        print(f"[{self.chat_id}] Loaded {len(self.messages)} messages.")

        if os.path.isdir(self.media_dir) and ocr_utils.OCR_AVAILABLE:
            ocr_utils.build_image_ocr_index_for_chat(self)
        else:
            print(f"[{self.chat_id}] Media dir missing or OCR disabled; skipping OCR.")


CHATS = {}  # chat_id -> ChatState


def discover_chats():
    """Find folders with _chat.txt and Media/ under CHAT_ROOT."""
    chats = []
    for name in sorted(os.listdir(config.CHAT_ROOT)):
        path = os.path.join(config.CHAT_ROOT, name)
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
    base_dir = os.path.join(config.CHAT_ROOT, chat_id)
    if not os.path.isdir(base_dir):
        return None
    chat = ChatState(chat_id, base_dir)
    chat.load()
    CHATS[chat_id] = chat
    return chat
