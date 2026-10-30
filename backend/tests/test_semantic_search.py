import importlib
from types import SimpleNamespace


def test_get_db_connection_uses_fresh_connection(monkeypatch):
    semantic_search = importlib.import_module("backend.retrieval.semantic_search")

    created = []

    class FakeConn:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    def fake_connect(**kwargs):
        conn = FakeConn()
        created.append(conn)
        return conn

    monkeypatch.setattr(semantic_search.psycopg2, "connect", fake_connect)

    first = semantic_search.get_db_connection()
    second = semantic_search.get_db_connection()

    assert first is not second
    assert len(created) == 2
    assert first.closed is False
    assert second.closed is False


def test_semantic_search_closes_connection_after_query(monkeypatch):
    semantic_search = importlib.import_module("backend.retrieval.semantic_search")

    class FakeCursor:
        def __init__(self):
            self.closed = False
            self.executed = False

        def execute(self, query, params):
            self.executed = True
            self.query = query
            self.params = params

        def fetchall(self):
            return [
                (
                    "chunk-1",
                    1,
                    "ordinance",
                    "1.1",
                    "Admission requires completion of registration formalities.",
                    10,
                    10,
                    "1",
                    "ADMISSION",
                    "UG Ordinance.pdf",
                    "UG_ORDINANCE_2023",
                    "BOG-73.13(A)-2023-08-10",
                    "742f71b5ce832a7b4adf0372b7caf678eef52766fa239c1075ae334079adc90c",
                    "Admission Procedure",
                    0.95,
                )
            ]

        def close(self):
            self.closed = True

    class FakeConn:
        def __init__(self):
            self.closed = False
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def close(self):
            self.closed = True

    fake_conn = FakeConn()

    monkeypatch.setattr(
        semantic_search,
        "model",
        SimpleNamespace(encode=lambda question, normalize_embeddings=True: [0.1, 0.2, 0.3]),
    )
    monkeypatch.setattr(semantic_search, "CANDIDATE_K", 1)
    monkeypatch.setattr(semantic_search, "TOP_K", 1)
    monkeypatch.setattr(semantic_search.psycopg2, "connect", lambda **kwargs: fake_conn)

    result = semantic_search.semantic_search("What are the admission criteria?")

    assert len(result) == 1
    assert result[0]["chunk_id"] == "chunk-1"
    assert result[0]["source_file"] == "UG Ordinance.pdf"
    assert result[0]["clause_title"] == "Admission Procedure"
    assert "kc.metadata->>'source_file' = %s" in fake_conn.cursor_obj.query
    assert fake_conn.cursor_obj.params[1] == "UG Ordinance.pdf"
    assert fake_conn.closed is True
    assert fake_conn.cursor_obj.closed is True


def test_semantic_search_filters_to_selected_ordinance(monkeypatch):
    semantic_search = importlib.import_module("backend.retrieval.semantic_search")

    class FakeCursor:
        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def close(self):
            pass

    connection = FakeConn()
    monkeypatch.setattr(
        semantic_search,
        "model",
        SimpleNamespace(
            encode=lambda question, normalize_embeddings=True: [0.1, 0.2, 0.3]
        ),
    )
    monkeypatch.setattr(
        semantic_search,
        "get_db_connection",
        lambda: connection,
    )

    assert semantic_search.semantic_search(
        "doctoral research progress",
        programme="PHD",
    ) == []
    assert connection.cursor_obj.params[1] == (
        "Ordinances_for_Doctoral_Programm2023.pdf"
    )


def test_semantic_search_uses_only_requested_approved_source_ids(monkeypatch):
    semantic_search = importlib.import_module("backend.retrieval.semantic_search")
    policy_registry = importlib.import_module(
        "backend.services.application_policy_registry"
    )

    class FakeCursor:
        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def close(self):
            pass

    connection = FakeConn()
    monkeypatch.setattr(
        policy_registry,
        "load_application_policy_registry",
        lambda: {
            "status": "AVAILABLE",
            "sources": [
                {
                    "source_id": "SYNTHETIC_MTECH",
                    "source_file": "synthetic-mtech.txt",
                    "programme": "MTECH",
                    "approval_status": "APPROVED",
                },
                {
                    "source_id": "OTHER_MTECH",
                    "source_file": "other-mtech.txt",
                    "programme": "MTECH",
                    "approval_status": "APPROVED",
                },
            ],
        },
    )
    monkeypatch.setattr(
        semantic_search,
        "model",
        SimpleNamespace(
            encode=lambda question, normalize_embeddings=True: [0.1, 0.2, 0.3]
        ),
    )
    monkeypatch.setattr(
        semantic_search,
        "get_db_connection",
        lambda: connection,
    )

    assert semantic_search.semantic_search(
        "synthetic M.Tech application",
        programme="MTECH",
        source_ids=["SYNTHETIC_MTECH"],
    ) == []
    assert (
        "kc.metadata->>'source_file' = ANY(%s)"
        in connection.cursor_obj.query
    )
    assert connection.cursor_obj.params[1] == ["synthetic-mtech.txt"]


def test_clause_title_contributes_to_keyword_relevance():
    semantic_search = importlib.import_module("backend.retrieval.semantic_search")

    score = semantic_search.calculate_keyword_score(
        "What is the attendance requirement?",
        "The minimum percentage must be maintained.",
        "PROGRAMME REQUIREMENTS",
    )
    titled_score = semantic_search.calculate_keyword_score(
        "What is the attendance requirement?",
        "The minimum percentage must be maintained.",
        "PROGRAMME REQUIREMENTS",
        "Attendance Requirement",
    )

    assert titled_score > score
