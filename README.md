# WhatsApp Export Chat Viewer

This is a simple WhatsApp export chat viewer that allows you to view your exported WhatsApp chat in a web browser.

## Features

- View your exported WhatsApp chat in a web browser.
- Search for images by their text content.
- Search for messages by text or name.

## Prerequisites

- Python 3.10+
- Tesseract OCR

## Setup

1. Clone the repository
2. Install the dependencies
3. Follow chat preparation instructions to prepare the chat for viewing.
4. Set the `CHAT_ROOT` variable in the `app.py` file to the path of the chat folder. (Default is `chats`)
5. Set the `SELF_NAME` variable in the `app.py` file to your own name as appears in WhatsApp export.
6. Run the application
7. Open the browser and navigate to `http://localhost:5000`
8. Select a chat folder from the picker.
9. View the chat.
10. Search for images by their text content.
11. Search for messages by text or name.
12. Filter messages by date range.

## Chat Preparation

1. Export the chat from WhatsApp.
2. Copy the chat folder to the `chats` folder.
3. Copy all media files to `chats/Media` folder.
4. Make sure the `_chat.txt` file is present in the chat folder.

## Folder Structure

```
app.py
templates/
  - base.html
  - chat.html
  - picker.html
static/
  - css/
    - style.css
  - js/
    - chat.js
chats/
  - Person1 Chats/
    - _chat.txt
    - Media/
      - image1.jpg
      - image2.jpg
      - image3.jpg
  - Person2 Chats/
    - _chat.txt
    - Media/
      - image4.jpg
      - image5.jpg
      - image6.jpg
```

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
