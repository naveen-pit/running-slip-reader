"""Main entry point of a project."""

from decimal import Decimal
import io

import functions_framework
from flask import Flask, Request
from flask import request as req
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    SourceGroup,
    SourceRoom,
    TextMessage,
    TextSendMessage,
    ImageMessage,
)
import numpy as np
import easyocr
from .config import cfg
from PIL import Image

# Initialize the EasyOCR reader
reader = easyocr.Reader(["en"], gpu=False)


def process_event(event: MessageEvent, line_bot_api: LineBotApi) -> str | None:
    if isinstance(event, MessageEvent) and (
        isinstance(event.message, TextMessage) or isinstance(event.message, ImageMessage)
    ):
        chat_id = (
            event.source.group_id
            if isinstance(event.source, SourceGroup)
            else event.source.room_id if isinstance(event.source, SourceRoom) else event.source.user_id
        )
        message_id = event.message.id
        if isinstance(event.message, TextMessage):
            messages = event.message.text.strip()
        elif isinstance(event.message, ImageMessage):
            message_content = line_bot_api.get_message_content(message_id)
            # Read the image content into memory
            image_bytes = io.BytesIO(message_content.content)

            # Open the image using PIL
            image = Image.open(image_bytes)

            distance = get_distance_easyocr(image)
            messages = "no distance can be extracted" if distance <= 0 else f"{str(distance)} km"

        print(event.message)
        reply_token = event.reply_token

        line_bot_api.reply_message(reply_token, TextSendMessage(text=messages))

        return messages
    return None


# Read text from an image
import easyocr

# Create an OCR reader object
reader = easyocr.Reader(["en"])


def get_distance_easyocr(image: Image):
    # Convert the image to an appropriate format for easyocr
    # Note: easyocr can work directly with numpy arrays, so we'll convert the image to a numpy array
    image_np = np.array(image)
    result = reader.readtext(image_np)
    distance_list = []
    prev_text = ""
    for detection in result:
        text: str = detection[1]
        text = text.strip().lower()
        text = text.replace("/km", "")
        text = text.replace("km/", "")
        # if contain only km, the distance might be in previous text.
        if text == "km":
            text = prev_text + text

        if "km" in text:
            distance = get_number_before_km(text)
            try:
                distance = float(distance)
                distance_list.append(distance)
            except:
                print(text)
                print("not a float")
        prev_text = text
    if len(distance_list) == 1:
        return distance_list[0]
    return -1


import re


def get_number_before_km(text):
    pattern = r"(\d+\.?\d*)\s*km"

    match = re.search(pattern, text)
    if match:
        number_before_km = match.group(1)
        return number_before_km
    return ""


@functions_framework.http
def reply(request: Request) -> str:
    main(request)
    return "OK"


def main(request: Request) -> str | None:
    channel_secret = cfg.line_channel_secret_key.get_secret_value()
    channel_access_token = cfg.line_access_token.get_secret_value()
    line_bot_api = LineBotApi(channel_access_token)
    parser = WebhookParser(channel_secret)
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = request.get_data(as_text=True)

    # parse webhook body
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise RuntimeError from None

    # if event is MessageEvent and message is TextMessage, then echo text
    for event in events:
        process_event(event, line_bot_api)

    return "OK"


app = Flask(__name__)


@app.route("/", methods=["GET"])
def home() -> str:
    return "LINE BOT HOME"


@app.route("/", methods=["POST"])
def callback() -> str:
    main(req)
    return "OK"
