from types import SimpleNamespace

import backend.database.seed_local_development as seeder


class FakeCursor:
    def __init__(self):
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params=None):
        self.query = query

    def fetchall(self):
        return []

    def fetchone(self):
        if "nextval(" in self.query:
            return (700,)
        return None


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        pass


def test_seed_uses_documented_synthetic_password_environment_variables(
    monkeypatch,
):
    expected_passwords = {
        "synthetic.student": "student-password",
        "synthetic.official": "official-password",
        "synthetic.dugc": "dugc-password",
    }
    environment_names = {
        "synthetic.student": "DEPARTMENTAI_SEED_STUDENT_PASSWORD",
        "synthetic.official": "DEPARTMENTAI_SEED_OFFICIAL_PASSWORD",
        "synthetic.dugc": "DEPARTMENTAI_SEED_DUGC_PASSWORD",
    }
    for username, environment_name in environment_names.items():
        monkeypatch.setenv(environment_name, expected_passwords[username])

    monkeypatch.setattr(
        seeder,
        "get_database_settings",
        lambda: SimpleNamespace(
            environment="development",
            database=seeder.LOCAL_DATABASES["development"],
        ),
    )
    monkeypatch.setattr(seeder, "get_connection", FakeConnection)
    captured_passwords = {}

    def capture_user(_cursor, username, _role, _subject, password):
        captured_passwords[username] = password
        return len(captured_passwords)

    monkeypatch.setattr(seeder, "_ensure_user", capture_user)

    application_id, _student_id = seeder.seed_local_development()

    assert application_id == 700
    assert captured_passwords == expected_passwords
