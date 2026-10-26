"""Arama ve sohbet uçları (sözleşme §5): POST /search, POST /chat/ask, GET /chat/conversations[/{id}]."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.api.helpers import (
    CHAT_ANSWER_KEYS,
    CONVERSATION_KEYS,
    MESSAGE_KEYS,
    OTHER_ADMIN,
    PAGE_KEYS,
    act_as,
    assert_error_shape,
    assert_source,
    assert_utc,
)

SEARCH = "/api/v1/search"
ASK = "/api/v1/chat/ask"
CONVS = "/api/v1/chat/conversations"
QUESTION = "Vibrasyon testi kaç saat sürmeli?"


def _ask(c: TestClient, **body) -> dict:
    r = c.post(ASK, json={"question": QUESTION, "standard_ids": [1], **body})
    assert r.status_code == 200, r.text
    return r.json()


# ============================================================================================= POST /search


def test_search_sourced_results(client: TestClient) -> None:
    r = client.post(SEARCH, json={"query": "vibrasyon testi süresi", "standard_ids": [1], "top_k": 5,
                                  "mode": "hybrid"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"query", "mode", "results", "duration_ms"}
    assert body["query"] == "vibrasyon testi süresi"
    assert body["mode"] == "hybrid"
    assert isinstance(body["duration_ms"], int) and body["duration_ms"] >= 0
    results = body["results"]
    assert 1 <= len(results) <= 5
    for src in results:
        assert_source(src)
        assert src["standard_id"] == 1 and src["standard_code"] == "MIL-STD-810H"
    scores = [s["score"] for s in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["section"] == "Method 514.8"  # vibrasyon → titreşim bölümü en üstte
    assert len({s["chunk_id"] for s in results}) == len(results)


def test_search_defaults(client: TestClient) -> None:
    body = client.post(SEARCH, json={"query": "vibration"}).json()
    assert body["mode"] == "hybrid"
    assert len(body["results"]) == 5  # top_k varsayılan 5


@pytest.mark.parametrize("top_k", [1, 2, 20])
def test_search_top_k_limit(client: TestClient, top_k: int) -> None:
    body = client.post(SEARCH, json={"query": "test", "top_k": top_k}).json()
    assert len(body["results"]) <= top_k
    if top_k <= 13:  # seed'de 810H (8) + 461G (5) = 13 parça
        assert len(body["results"]) == top_k


def test_search_is_deterministic(client: TestClient) -> None:
    payload = {"query": "sıcaklık depolama", "standard_ids": [], "top_k": 10}
    a = client.post(SEARCH, json=payload).json()
    b = client.post(SEARCH, json=payload).json()
    assert a["results"] == b["results"]


def test_search_empty_standard_ids_means_all_indexed(client: TestClient) -> None:
    for payload in ({"query": "test", "standard_ids": [], "top_k": 20}, {"query": "test", "top_k": 20}):
        results = client.post(SEARCH, json=payload).json()["results"]
        assert {s["standard_id"] for s in results} == {1, 2}  # DO-178C (indekslenmemiş) yok


def test_search_only_not_indexed_standard_empty(client: TestClient) -> None:
    r = client.post(SEARCH, json={"query": "software level DAL", "standard_ids": [3]})
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_unknown_standard_ids_skipped(client: TestClient) -> None:
    # Geliştirici kararı: olmayan standart sessizce atlanır (sözleşmede tanımsız → rapordaki soru).
    r = client.post(SEARCH, json={"query": "vibration", "standard_ids": [999]})
    assert r.status_code == 200 and r.json()["results"] == []


@pytest.mark.parametrize("mode", ["semantic", "keyword", "hybrid"])
def test_search_modes(client: TestClient, mode: str) -> None:
    body = client.post(SEARCH, json={"query": "vibration", "mode": mode}).json()
    assert body["mode"] == mode


def test_search_query_boundaries(client: TestClient) -> None:
    assert client.post(SEARCH, json={"query": "ab"}).status_code == 200
    assert client.post(SEARCH, json={"query": "x" * 500}).status_code == 200


@pytest.mark.parametrize("payload", [
    {"query": "a"}, {"query": "x" * 501}, {}, {"query": "vibration", "top_k": 0}, {"query": "vibration", "top_k": 21},
    {"query": "vibration", "mode": "fuzzy"}, {"query": "vibration", "standard_ids": ["bir"]},
])
def test_search_invalid_422(client: TestClient, payload: dict) -> None:
    err = assert_error_shape(client.post(SEARCH, json=payload), 422, "VALIDATION_ERROR")
    assert err["details"]


# ============================================================================================= POST /chat/ask


def test_ask_new_conversation_answered(client: TestClient) -> None:
    body = _ask(client)
    assert set(body) == CHAT_ANSWER_KEYS
    assert body["status"] == "ANSWERED"
    assert body["question"] == QUESTION
    assert body["answer"].startswith("[DEMO]")
    assert body["sources"]
    for src in body["sources"]:
        assert_source(src)
    assert body["model"] == "mock-llm"
    assert isinstance(body["conversation_id"], int) and isinstance(body["message_id"], int)
    assert body["duration_ms"] >= 0
    assert_utc(body["created_at"])
    # Cevap en iyi kaynağı gösteriyor.
    assert body["sources"][0]["standard_code"] in body["answer"]


def test_ask_top_k_limits_sources(client: TestClient) -> None:
    assert len(_ask(client, top_k=2)["sources"]) == 2


def test_ask_same_conversation_twice(client: TestClient) -> None:
    first = _ask(client)
    second = _ask(client, conversation_id=first["conversation_id"], question="Kaç eksende uygulanır?")
    assert second["conversation_id"] == first["conversation_id"]
    assert second["message_id"] != first["message_id"]
    convs = client.get(CONVS).json()
    assert convs["total"] == 1
    assert convs["items"][0]["message_count"] == 2
    detail = client.get(f"{CONVS}/{first['conversation_id']}").json()
    assert detail["message_count"] == 2
    assert [m["id"] for m in detail["messages"]] == [first["message_id"], second["message_id"]]  # eskiden yeniye


def test_ask_unknown_conversation_404(client: TestClient) -> None:
    r = client.post(ASK, json={"question": QUESTION, "conversation_id": 999})
    assert_error_shape(r, 404, "NOT_FOUND")
    assert client.get(CONVS).json()["total"] == 0  # yeni sohbet açılmadı


def test_ask_only_not_indexed_standard_no_results(client: TestClient) -> None:
    body = _ask(client, standard_ids=[3], question="DAL-A yazılım seviyesi nedir?")
    assert body["status"] == "NO_RESULTS"
    assert body["answer"] is None
    assert body["sources"] == []


def test_ask_empty_standard_ids_uses_all(client: TestClient) -> None:
    body = _ask(client, standard_ids=[], top_k=20, question="test gereksinimleri")
    assert body["status"] == "ANSWERED"
    assert {s["standard_id"] for s in body["sources"]} == {1, 2}


def test_ask_llm_unavailable(make_client) -> None:
    c = make_client(LLM_PROVIDER="gemini")
    body = _ask(c)
    assert body["status"] == "LLM_UNAVAILABLE"
    assert body["answer"] is None
    assert body["sources"]
    for src in body["sources"]:
        assert_source(src)
    # Mesaj yine de geçmişe kaydedilir.
    detail = c.get(f"{CONVS}/{body['conversation_id']}").json()
    assert detail["messages"][0]["status"] == "LLM_UNAVAILABLE"
    assert detail["messages"][0]["answer"] is None


@pytest.mark.parametrize("payload", [
    {"question": "ne"}, {"question": "x" * 2001}, {}, {"question": QUESTION, "top_k": 21},
    {"question": QUESTION, "conversation_id": "bir"},
])
def test_ask_invalid_422(client: TestClient, payload: dict) -> None:
    assert_error_shape(client.post(ASK, json=payload), 422, "VALIDATION_ERROR")


def test_ask_question_boundaries(client: TestClient) -> None:
    assert client.post(ASK, json={"question": "abc"}).status_code == 200
    assert client.post(ASK, json={"question": "y" * 2000}).status_code == 200


# ============================================================================================= GET /chat/conversations


def test_conversations_empty_initially(client: TestClient) -> None:
    body = client.get(CONVS).json()
    assert set(body) == PAGE_KEYS
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_conversations_list_after_ask(client: TestClient) -> None:
    long_q = "Titreşim testinde rastgele vibrasyon profili her eksende ne kadar süre uygulanmalıdır ve neden?"
    assert len(long_q) > 60
    ans = _ask(client, question=long_q)
    body = client.get(CONVS).json()
    assert body["total"] == 1
    conv = body["items"][0]
    assert set(conv) == CONVERSATION_KEYS
    assert conv["id"] == ans["conversation_id"]
    assert conv["title"] == long_q[:60]
    assert conv["message_count"] == 1
    assert conv["standard_ids"] == [1]
    assert_utc(conv["created_at"])
    assert_utc(conv["updated_at"])


def test_conversations_short_title_kept(client: TestClient) -> None:
    _ask(client)
    assert client.get(CONVS).json()["items"][0]["title"] == QUESTION


def test_conversations_newest_first_and_paged(client: TestClient) -> None:
    a = _ask(client, question="Birinci soru nedir?")
    b = _ask(client, question="İkinci soru nedir?")
    body = client.get(CONVS).json()
    assert [c["id"] for c in body["items"]] == [b["conversation_id"], a["conversation_id"]]
    page = client.get(CONVS, params={"page": 2, "page_size": 1}).json()
    assert page["total"] == 2 and page["page"] == 2 and page["page_size"] == 1
    assert [c["id"] for c in page["items"]] == [a["conversation_id"]]
    # Eski sohbete yeni mesaj gelince en üste çıkar.
    _ask(client, conversation_id=a["conversation_id"], question="Devam sorusu?")
    assert client.get(CONVS).json()["items"][0]["id"] == a["conversation_id"]


@pytest.mark.parametrize("params", [{"page_size": 101}, {"page": 0}, {"page_size": "çok"}])
def test_conversations_invalid_paging_422(client: TestClient, params: dict) -> None:
    assert_error_shape(client.get(CONVS, params=params), 422, "VALIDATION_ERROR")


# ============================================================================================= GET /chat/conversations/{id}


def test_conversation_detail(client: TestClient) -> None:
    ans = _ask(client)
    r = client.get(f"{CONVS}/{ans['conversation_id']}")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == CONVERSATION_KEYS | {"messages"}
    assert body["id"] == ans["conversation_id"]
    assert body["message_count"] == 1 == len(body["messages"])
    msg = body["messages"][0]
    assert set(msg) == MESSAGE_KEYS
    assert msg["id"] == ans["message_id"]
    assert msg["question"] == QUESTION and msg["answer"] == ans["answer"] and msg["status"] == "ANSWERED"
    assert msg["sources"] == ans["sources"]
    assert_utc(msg["created_at"])


def test_conversation_detail_404(client: TestClient) -> None:
    assert_error_shape(client.get(f"{CONVS}/999"), 404, "NOT_FOUND")


def test_conversation_detail_non_int_422(client: TestClient) -> None:
    assert_error_shape(client.get(f"{CONVS}/abc"), 422, "VALIDATION_ERROR")


def test_other_users_conversation_is_hidden(app: FastAPI, client: TestClient) -> None:
    ans = _ask(client)  # demo kullanıcı
    cid = ans["conversation_id"]
    act_as(app, OTHER_ADMIN)  # ADMIN bile olsa başkasının sohbetini göremez
    assert_error_shape(client.get(f"{CONVS}/{cid}"), 404, "NOT_FOUND")
    assert_error_shape(client.post(ASK, json={"question": QUESTION, "conversation_id": cid}), 404, "NOT_FOUND")
    assert client.get(CONVS).json()["total"] == 0
    app.dependency_overrides.clear()
    assert client.get(f"{CONVS}/{cid}").json()["message_count"] == 1  # sahibinin sohbeti bozulmadı


# ============================================================================================= düzeltilmiş bulgular


def test_conversation_standard_ids_drop_unknown(client: TestClient) -> None:
    ans = _ask(client, standard_ids=[3, 999], question="DAL-A seviyesi nedir?")
    assert ans["status"] == "NO_RESULTS"  # aramada sessiz atlama aynen
    conv = client.get(CONVS).json()["items"][0]
    assert conv["standard_ids"] == [3]
    assert client.get(f"{CONVS}/{ans['conversation_id']}").json()["standard_ids"] == [3]


def test_conversation_standard_ids_merge_known_only(client: TestClient) -> None:
    ans = _ask(client, standard_ids=[999])
    _ask(client, conversation_id=ans["conversation_id"], standard_ids=[2, 1, 888], question="Devam sorusu?")
    assert client.get(f"{CONVS}/{ans['conversation_id']}").json()["standard_ids"] == [1, 2]


@pytest.mark.parametrize("question", ["   ", "\t\n ", " a "])
def test_ask_whitespace_only_or_short_after_trim_422(client: TestClient, question: str) -> None:
    assert_error_shape(client.post(ASK, json={"question": question}), 422, "VALIDATION_ERROR")
    assert client.get(CONVS).json()["total"] == 0


@pytest.mark.parametrize("query", ["   ", "  a  "])
def test_search_whitespace_only_or_short_after_trim_422(client: TestClient, query: str) -> None:
    assert_error_shape(client.post(SEARCH, json={"query": query}), 422, "VALIDATION_ERROR")


def test_ask_title_trimmed(client: TestClient) -> None:
    _ask(client, question="   Vibrasyon testi kaç saat?   ")
    assert client.get(CONVS).json()["items"][0]["title"] == "Vibrasyon testi kaç saat?"
