import asyncio
import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from packages.common.models import Base, User
from services.auth_service.app import create_app


class AuthServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)
        cls.engine: AsyncEngine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        cls.session_factory = async_sessionmaker(bind=cls.engine, expire_on_commit=False)

        cls.loop.run_until_complete(cls._prepare_database())
        cls.app = create_app(engine=cls.engine, session_factory=cls.session_factory)
        cls.client = TestClient(cls.app)

    @classmethod
    async def _prepare_database(cls) -> None:
        async with cls.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: User.__table__.drop(sync_conn, checkfirst=True))
            await conn.run_sync(lambda sync_conn: User.__table__.create(sync_conn, checkfirst=True))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.loop.run_until_complete(cls.engine.dispose())
        cls.loop.close()

    def test_signup_and_login_flow(self) -> None:
        email = f"user+{uuid.uuid4().hex}@test.com"
        password = "Passw0rd!"

        response = self.client.post(
            "/auth/signup",
            json={"email": email, "password": password, "display_name": "User"},
        )
        self.assertEqual(response.status_code, 201, response.text)

        login_response = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)
        token = login_response.json()["access_token"]

        me_response = self.client.get(
            "/auth/me",
            headers={"authorization": f"Bearer {token}"},
        )
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["email"], email)

    def test_signup_conflict(self) -> None:
        email = f"duplicate+{uuid.uuid4().hex}@test.com"
        password = "Passw0rd!"

        first = self.client.post(
            "/auth/signup",
            json={"email": email, "password": password},
        )
        self.assertEqual(first.status_code, 201, first.text)

        duplicate = self.client.post(
            "/auth/signup",
            json={"email": email, "password": password},
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

    def test_login_invalid_password(self) -> None:
        email = f"wrongpass+{uuid.uuid4().hex}@test.com"
        password = "Passw0rd!"

        self.client.post(
            "/auth/signup",
            json={"email": email, "password": password},
        )

        bad_login = self.client.post(
            "/auth/login",
            json={"email": email, "password": "incorrect"},
        )
        self.assertEqual(bad_login.status_code, 401, bad_login.text)


if __name__ == "__main__":
    unittest.main()
