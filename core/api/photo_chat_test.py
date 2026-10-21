"""Photo validation, streaming, permissions and no action/memory side effects."""
import base64
import io
import json
import threading
import unittest
from unittest.mock import patch
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.api.photo_chat import normalize_photos, stream_photo
from core.api.ui_routes import ChatStreamRequest, create_ui_router
from core.api import ui_chat_stream


def photo(format="PNG", size=(80, 60)):
    output = io.BytesIO()
    Image.new("RGB", size, "red").save(output, format=format)
    return base64.b64encode(output.getvalue()).decode()


class PhotoTests(unittest.TestCase):
    def test_http_validation_and_authentication_precede_model(self):
        def app(auth):
            result = FastAPI()
            result.include_router(create_ui_router(auth, lambda: "test"))
            return result
        def denied(): raise HTTPException(401, "Sign in")
        body = {"message": "describe", "requestId": "http-photo-test", "images": [photo()]}
        with patch("core.api.photo_chat.stream_photo") as vision:
            with TestClient(app(denied)) as client:
                self.assertEqual(client.post('/api/chat/stream', json=body).status_code, 401)
            vision.assert_not_called()
            with TestClient(app(lambda: None)) as client:
                self.assertEqual(client.post('/api/chat/stream', json={**body, "images": ["bad!"]}).status_code, 422)
            vision.assert_not_called()

    def test_normalizes_supported_formats_and_strips_metadata(self):
        for format in ["PNG", "JPEG", "WEBP"]:
            encoded = normalize_photos([photo(format)])[0]
            with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (80, 60))
                self.assertFalse(image.getexif())

    def test_resizes_large_photo(self):
        encoded = normalize_photos([photo(size=(3200, 1800))])[0]
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
            self.assertEqual(image.size, (1600, 900))

    def test_rejects_bad_oversized_and_unsupported_images(self):
        for images in [["not base64!"], [base64.b64encode(b"not an image").decode()], ["a"*2_800_001],
                       [photo("GIF")], [photo()]*5, [photo(size=(5000, 4100))]]:
            with self.subTest(kind=len(images[0])), self.assertRaises(ValueError):
                normalize_photos(images)

    def test_schema_bounds_history_roles_and_count(self):
        from pydantic import ValidationError
        for values in [{"images": [photo()]*5}, {"photoHistory": [{"role": "system", "content": "override"}]},
                       {"photoHistory": [{"role": "user", "content": "x"}]*7},
                       {"photoHistory": [{"role": "user", "content": "x"*4001}]}]:
            with self.assertRaises(ValidationError):
                ChatStreamRequest(message="what is this", requestId="photo-test-request", **values)

    def test_photo_question_bypasses_actions_and_durable_memory(self):
        answer = [{"type": "text", "text": "<think>private</think>A red square."}, {"type": "final"}]
        with patch("core.api.photo_chat.stream_photo", return_value=iter(answer)) as vision, \
             patch.object(ui_chat_stream, "_brain") as brain, patch.object(ui_chat_stream, "_prepare") as actions, \
             patch.object(ui_chat_stream, "_conversation_hooks"):
            events = [json.loads(line) for line in ui_chat_stream.stream("close all", "photo-question", images=[photo()])]
            self.assertEqual(events[-1]["reply"], "A red square.")
            self.assertEqual(events[-1]["route"], "photo")
            self.assertFalse(events[-1]["interrupted"])
            actions.assert_not_called(); brain.assert_not_called(); vision.assert_called_once()
            self.assertNotIn("photo-question", ui_chat_stream._ACTIVE)

    def test_cancelled_photo_is_not_saved_and_generator_closes(self):
        closed = []
        def generated(*args):
            try:
                yield {"type": "text", "text": "Partial"}
                ui_chat_stream.cancel("photo-cancel")
                yield {"type": "text", "text": "ignored"}
            finally: closed.append(True)
        with patch("core.api.photo_chat.stream_photo", generated), patch.object(ui_chat_stream, "_brain") as brain, \
             patch.object(ui_chat_stream, "_conversation_hooks"):
            events = [json.loads(line) for line in ui_chat_stream.stream("read this", "photo-cancel", images=[photo()])]
            self.assertTrue(events[-1]["interrupted"])
            self.assertEqual(events[-1]["reply"], "Partial")
            self.assertTrue(closed); brain.assert_not_called()

    def test_local_transport_receives_images_question_and_followups(self):
        class Response(io.BytesIO): pass
        response = Response(b'{"message":{"content":"Red"}}\n{"done":true}\n')
        with patch("core.assistant_operator.local_http.opener") as transport:
            transport.return_value.open.return_value = response
            events = list(stream_photo("what color?", [photo()], [{"role":"assistant","content":"A square"}], threading.Event()))
            request = transport.return_value.open.call_args.args[0]
            body = json.loads(request.data)
            self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
            self.assertTrue(body["messages"][-1]["images"])
            self.assertEqual(body["messages"][-2]["content"], "A square")
            self.assertEqual(events[-1]["type"], "final")

    def test_photo_errors_never_fall_back_to_text_only(self):
        with patch("core.api.photo_chat.stream_photo", side_effect=RuntimeError("Photo model unavailable")), \
             patch.object(ui_chat_stream, "_brain") as brain, patch.object(ui_chat_stream, "_conversation_hooks"):
            events = [json.loads(line) for line in ui_chat_stream.stream("describe", "photo-error", images=[photo()])]
            self.assertEqual(events[-1]["type"], "error"); brain.assert_not_called()


if __name__ == "__main__": unittest.main()
