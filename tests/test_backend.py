import asyncio
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from PIL import Image

import backend


class DefaultModelTests(unittest.TestCase):
    def test_falls_back_when_evaluation_is_unavailable(self) -> None:
        available = {"fallback": Path("models/fallback/weights/best.pt")}
        with (
            patch.object(backend, "_available_models", return_value=available),
            patch.object(
                backend,
                "_read_evaluation",
                side_effect=HTTPException(status_code=503),
            ),
        ):
            self.assertEqual(backend._default_model_name(), "fallback")

    def test_falls_back_when_recommendation_is_not_available(self) -> None:
        available = {"fallback": Path("models/fallback/weights/best.pt")}
        evaluation = {
            "detectors": [
                {"status": "recommended", "checkpoint": "loose:missing.pt"}
            ]
        }
        with (
            patch.object(backend, "_available_models", return_value=available),
            patch.object(backend, "_read_evaluation", return_value=evaluation),
        ):
            self.assertEqual(backend._default_model_name(), "fallback")


class RequestSizeLimitTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _scope(content_length: int | None = None) -> dict:
        headers = []
        if content_length is not None:
            headers.append((b"content-length", str(content_length).encode()))
        return {
            "type": "http",
            "method": "POST",
            "path": "/predict",
            "headers": headers,
        }

    async def test_rejects_large_content_length_before_downstream(self) -> None:
        downstream_called = False

        async def downstream(scope, receive, send) -> None:
            nonlocal downstream_called
            downstream_called = True

        async def receive() -> dict:
            raise AssertionError("Body should not be read")

        sent = []

        async def send(message: dict) -> None:
            sent.append(message)

        middleware = backend.RequestSizeLimitMiddleware(downstream, max_body_size=5)
        await middleware(self._scope(content_length=6), receive, send)

        self.assertFalse(downstream_called)
        self.assertEqual(sent[0]["status"], 413)

    async def test_cors_headers_are_added_to_early_rejection(self) -> None:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/predict",
            "raw_path": b"/predict",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"content-length", str(backend.MAX_REQUEST_BYTES + 1).encode()),
                (b"origin", b"http://localhost:3000"),
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        }

        async def receive() -> dict:
            raise AssertionError("Body should not be read")

        sent = []

        async def send(message: dict) -> None:
            sent.append(message)

        await backend.app(scope, receive, send)

        response_start = next(
            message for message in sent if message["type"] == "http.response.start"
        )
        headers = dict(response_start["headers"])
        self.assertEqual(response_start["status"], 413)
        self.assertEqual(headers[b"access-control-allow-origin"], b"http://localhost:3000")

    async def test_rejects_chunked_body_before_downstream(self) -> None:
        downstream_called = False
        chunks = iter(
            [
                {"type": "http.request", "body": b"abc", "more_body": True},
                {"type": "http.request", "body": b"def", "more_body": False},
            ]
        )

        async def downstream(scope, receive, send) -> None:
            nonlocal downstream_called
            downstream_called = True

        async def receive() -> dict:
            return next(chunks)

        sent = []

        async def send(message: dict) -> None:
            sent.append(message)

        middleware = backend.RequestSizeLimitMiddleware(downstream, max_body_size=5)
        await middleware(self._scope(), receive, send)

        self.assertFalse(downstream_called)
        self.assertEqual(sent[0]["status"], 413)


class ImageDimensionTests(unittest.TestCase):
    @staticmethod
    def _image_bytes(width: int, height: int) -> bytes:
        output = BytesIO()
        Image.new("RGB", (width, height)).save(output, format="PNG")
        return output.getvalue()

    def test_accepts_image_within_limits(self) -> None:
        self.assertEqual(backend._validate_image_dimensions(self._image_bytes(4, 2)), (4, 2))

    def test_rejects_image_above_width_limit(self) -> None:
        with patch.object(backend, "MAX_IMAGE_WIDTH", 3):
            with self.assertRaises(HTTPException) as raised:
                backend._validate_image_dimensions(self._image_bytes(4, 2))
        self.assertEqual(raised.exception.status_code, 413)

    def test_corrupt_image_parser_error_returns_bad_request(self) -> None:
        with patch("PIL.Image.open", side_effect=SyntaxError("broken image")):
            with self.assertRaises(HTTPException) as raised:
                backend._validate_image_dimensions(b"corrupt")
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
