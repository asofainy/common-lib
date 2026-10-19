import unittest

from common_lib.errors import ServiceError, to_http_exception


class ServiceErrorTests(unittest.TestCase):
    def test_service_error_maps_to_http_exception(self):
        error = ServiceError("boom")
        http_error = to_http_exception(error)

        self.assertIsInstance(http_error, Exception)
        self.assertEqual(getattr(http_error, "status_code", 500), 500)
        self.assertEqual(getattr(http_error, "detail", str(http_error)), "boom")


if __name__ == "__main__":
    unittest.main()
