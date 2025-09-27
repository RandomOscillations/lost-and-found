import asyncio
import unittest

from packages.common import get_settings
from packages.common.jwt import decode_jwt, encode_jwt
from packages.common.security import hash_password, verify_password
from packages.common.utils.categories import infer_category


class TestCommonUtilities(unittest.TestCase):
    def test_settings_defaults(self) -> None:
        settings = get_settings()
        self.assertEqual(settings.app_name, "Lost&Found Vision")
        self.assertGreaterEqual(settings.default_match_limit, 1)

    def test_password_hash_roundtrip(self) -> None:
        password = "Passw0rd!"
        hashed = hash_password(password)
        self.assertNotEqual(hashed, password)
        self.assertTrue(verify_password(password, hashed))

    def test_jwt_roundtrip(self) -> None:
        token = encode_jwt("user-123", {"role": "tester"})
        payload = decode_jwt(token)
        self.assertEqual(payload["sub"], "user-123")
        self.assertEqual(payload["role"], "tester")

    def test_infer_category(self) -> None:
        category = infer_category(tags=["HydroFlask", "Blue"])
        self.assertEqual(category, "water_bottle")


if __name__ == "__main__":
    unittest.main()
