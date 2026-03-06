"""Camera capture and GPT-4o vision observation."""

import base64
import openai
import cv2

CAMERA_INDEX = 0
FRAME_SIZE = (320, 240)


def observe_and_comment() -> str:
    """Capture one frame, resize, send to GPT-4o chat with image; return one short comment."""
    cap = cv2.VideoCapture(CAMERA_INDEX)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return ""
    frame_small = cv2.resize(frame, FRAME_SIZE)
    _, buffer = cv2.imencode(".jpg", frame_small)
    b64 = base64.b64encode(buffer).decode("utf-8")

    # TODO: Add system prompt for eversti Sandels :DD
    response = openai.chat.completions.create(
        model="gpt-4o", # TODO: Possibly change model
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                    {
                        "type": "text",
                        "text": "You are a witty robot. Comment on what you see in one short sentence.",
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content or ""
