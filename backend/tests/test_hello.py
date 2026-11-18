import unittest
from fastapi.testclient import TestClient

from backend.main import app


class HelloBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint_returns_ok(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "ubnd-ai-backend")

    def test_hello_endpoint_returns_default_vietnamese_greeting(self) -> None:
        response = self.client.get("/api/hello")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data["message"],
            "Xin chào từ Backend Bộ Trợ lý AI UBND xã, phường!",
        )
        self.assertEqual(data["service"], "ubnd-ai-backend")

    def test_hello_endpoint_personalizes_greeting_with_name_query(self) -> None:
        response = self.client.get("/api/hello", params={"name": "UBND Phường Tân Bình"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data["message"],
            "Xin chào UBND Phường Tân Bình từ Backend Bộ Trợ lý AI!",
        )

    def test_cors_allows_frontend_origin(self) -> None:
        response = self.client.options(
            "/api/hello",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()

