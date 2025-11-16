# WhatsApp Export Chat Viewer

A simple and powerful WhatsApp export chat viewer that allows you to browse, search, and analyze your exported WhatsApp chats—right from your browser.

## Features
- Image search using OCR (Tesseract)
- Search messages by text or sender
- Filter messages by date
- Fast chat navigation
- Multiple exported chat folders

---

## RUN WITH DOCKER (Recommended)

You do **not** need Python or Tesseract installed locally. Everything runs inside Docker.

### 1. Pull the Docker image:

```
docker pull sohelshekhin/wp_export_chat_viewer:latest
```

### 2. Prepare your chats folder on your computer (see Chat Preparation below)

Example folder structure:

```
/home/user/chats/
    └── FamilyChat/
         ├── _chat.txt
         └── Media/
             ├── image1.jpg
             └── ...
```

### 3. Run the container with your chats mounted:

```
docker run -p 5000:5000   -v /home/user/chats:/data/chats   sohelshekhin/wp_export_chat_viewer:latest
```

Open in your browser:

```
http://localhost:5000
```

Your chat folders will appear in the picker automatically.

---

## ALTERNATIVE: COPY CHATS INTO CONTAINER

_Not recommended, but supported_

Run the container:

```
docker run -d -p 5000:5000 --name chatviewer sohelshekhin/wp_export_chat_viewer
```

Copy your chats:

```
docker cp chats/ chatviewer:/app/chats
```

Then open:

```
http://localhost:5000
```

---

## CHAT PREPARATION

### 1. Export the chat from WhatsApp  
WhatsApp → Chat → More → Export Chat → **WITH Media**

This generates:

```
_chat.txt
```

### 2. Create a folder for the chat:

```
/home/user/chats/FamilyChat/
```

### 3. Move `_chat.txt` inside the folder:

```
FamilyChat/_chat.txt
```

### 4. Create a Media folder for images and videos:

```
FamilyChat/Media/
    image1.jpg
    image2.jpg
```

### 5. Mount the parent folder into Docker:

```
docker run -p 5000:5000   -v /home/user/chats:/data/chats   sohelshekhin/wp_export_chat_viewer
```

---

## CONFIGURATION

`config.py` supports:

```
CHAT_ROOT = os.environ.get("CHAT_ROOT", "/data/chats")
SELF_NAME = "Your Name In WhatsApp Export"
```

Override CHAT_ROOT:

```
docker run -p 5000:5000   -e CHAT_ROOT=/data/chats   -v /home/user/chats:/data/chats   sohelshekhin/wp_export_chat_viewer
```

---

## FOLDER STRUCTURE

```
app.py
config.py
parsing.py
ocr_utils.py
meta_db.py
chat_state.py

templates/
    base.html
    chat.html
    picker.html

static/
    css/style.css
    js/chat.js

chats/ (optional for local runs)
```

---

## RUN LOCALLY (without Docker)

### Requirements:
- Python 3.10+
- Tesseract OCR installed

### Install dependencies:

```
pip install -r requirements.txt
```

### Run:

```
python app.py
```

Open:

```
http://localhost:5000
```

---

## LICENSE

MIT License
