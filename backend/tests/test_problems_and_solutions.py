# tests/test_problems_and_solutions.py
import pytest

# -----------------------------
# Helpers
# -----------------------------

def _unwrap(payload):
    """
    Tolerant extractor:
    - If backend returns {"data": {...|[...]}} -> return that
    - If backend returns {"questions": [...]}, return that
    - If backend returns {"solutions": [...]}, return that
    - If backend returns {"items": [...]}, return that
    - If backend returns {"item": {...}}, return that
    - Else return the payload as-is
    """
    if payload is None:
        return None
    if isinstance(payload, dict):
        if "data" in payload:
            return payload["data"]
        if "questions" in payload:
            return payload["questions"]
        if "solutions" in payload:
            return payload["solutions"]
        if "items" in payload:
            return payload["items"]
        if "item" in payload:
            return payload["item"]
    return payload


def _auth_register_and_login(client, email="admin@moringa.test", password="secret", name="Admin User"):
    # Register (ignore status; some backends may return 409 if already exists)
    client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    # Login
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.data
    token = r.get_json().get("access_token")
    assert token, "No access_token in /auth/login response"
    return {"Authorization": f"Bearer {token}"}


def _create_problem(
    client,
    headers,
    title="Typescript",
    description="What is TypeScript?",
    problem_type="language",
    tag_ids=None,
):
    payload = {
        "title": title,
        "description": description,
        "problem_type": problem_type,  # must be one of: language, stage, technical, logical
    }
    if tag_ids is not None:
        payload["tag_ids"] = tag_ids
    r = client.post("/problems", headers=headers, json=payload)
    assert r.status_code in (200, 201), r.data
    body = r.get_json()
    data = _unwrap(body)
    # Some implementations return the object directly
    if isinstance(body, dict) and "id" in body and not isinstance(data, (list, dict)):
        data = body
    assert isinstance(data, dict), f"Unexpected create_problem shape: {body}"
    assert data.get("id") is not None, f"No id in problem: {data}"
    return data


# -----------------------------
# Tests
# -----------------------------

def test_problem_crud_happy_path(client):
    """Create two problems, list them, fetch one by id."""
    headers = _auth_register_and_login(client)

    # Create with valid types
    p1 = _create_problem(client, headers, title="TS", description="What is TS?", problem_type="language")
    p2 = _create_problem(client, headers, title="JWT with React", description="How to JWT?", problem_type="technical")

    # List
    r = client.get("/problems", query_string={"page": 1, "per_page": 10})
    assert r.status_code == 200, r.data
    body = r.get_json()
    items = _unwrap(body)
    assert isinstance(items, list), f"Expected list from /problems, got: {body}"
    ids = {item.get("id") for item in items}
    assert p1["id"] in ids and p2["id"] in ids

    # Get one
    r = client.get(f"/problems/{p1['id']}")
    assert r.status_code == 200, r.data
    one = _unwrap(r.get_json())
    assert isinstance(one, dict)
    assert one.get("id") == p1["id"]
    assert (one.get("title") or "").lower() in ("ts", "typescript")


def test_problem_not_found(client):
    r = client.get("/problems/999999")
    # Prefer 404, but tolerate 200 with an error envelope if your handler wraps it.
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        payload = r.get_json()
        assert "error" in payload or "data" in payload


def test_search_and_filter(client):
    headers = _auth_register_and_login(client)

    # Use only allowed problem_type values
    _create_problem(client, headers, title="Docker basics", description="containers", problem_type="technical")
    _create_problem(client, headers, title="React basics", description="components", problem_type="stage")
    _create_problem(client, headers, title="Postgres tuning", description="db", problem_type="logical")

    # Search "React"
    r = client.get("/problems", query_string={"search": "React"})
    assert r.status_code == 200
    items = _unwrap(r.get_json())
    assert isinstance(items, list)
    assert any("react" in (it.get("title") or "").lower() for it in items)

    # Filter by a valid problem_type
    r = client.get("/problems", query_string={"problem_type": "stage"})
    assert r.status_code == 200
    items = _unwrap(r.get_json())
    assert all(it.get("problem_type") == "stage" for it in items)


def test_solutions_flow(client):
    headers = _auth_register_and_login(client)

    p = _create_problem(client, headers, title="Has answers", description="Body", problem_type="technical")

    # Initially empty
    r0 = client.get(f"/problems/{p['id']}/solutions", query_string={"page": 1, "per_page": 10})
    assert r0.status_code == 200, r0.data
    payload0 = r0.get_json()
    solutions0 = payload0.get("solutions") or _unwrap(payload0) or []
    assert isinstance(solutions0, list)
    assert len(solutions0) == 0

    # Create a solution
    r1 = client.post(
        f"/problems/{p['id']}/solutions",
        headers=headers,
        json={"content": "Use tsconfig and strict typing."},
    )
    assert r1.status_code in (200, 201), r1.data

    # List again
    r2 = client.get(f"/problems/{p['id']}/solutions")
    assert r2.status_code == 200, r2.data
    payload2 = r2.get_json()
    solutions2 = payload2.get("solutions") or _unwrap(payload2) or []
    assert isinstance(solutions2, list)
    assert len(solutions2) >= 1
    assert any(("tsconfig" in (s.get("content") or "").lower()) for s in solutions2)


def test_follow_unfollow(client):
    headers = _auth_register_and_login(client)
    p = _create_problem(client, headers, title="Follow me", description="Body", problem_type="technical")

    # Follow
    r1 = client.post(f"/problems/{p['id']}/follow", headers=headers)
    assert r1.status_code in (200, 201), r1.data

    # Duplicate follow should 400/409
    r_dup = client.post(f"/problems/{p['id']}/follow", headers=headers)
    assert r_dup.status_code in (400, 409), r_dup.data

    # Unfollow
    r2 = client.delete(f"/problems/{p['id']}/follow", headers=headers)
    assert r2.status_code in (200, 204), r2.data

    # Unfollow again → 404
    r3 = client.delete(f"/problems/{p['id']}/follow", headers=headers)
    assert r3.status_code == 404


def test_link_related(client):
    headers = _auth_register_and_login(client)
    a = _create_problem(client, headers, title="A", description="A", problem_type="language")
    b = _create_problem(client, headers, title="B", description="B", problem_type="language")

    # Link A ↔ B
    r = client.post(f"/problems/{a['id']}/related/{b['id']}", headers=headers)
    assert r.status_code in (200, 201), r.data

    # Fetch A and verify it includes related_questions
    r2 = client.get(f"/problems/{a['id']}")
    assert r2.status_code == 200, r2.data
    one = _unwrap(r2.get_json())
    if isinstance(one, dict):
        rq = one.get("related_questions", [])
        assert isinstance(rq, list)
        assert any(item.get("id") == b["id"] for item in rq), rq


def _extract_item(response_json):
    if not isinstance(response_json, dict):
        return response_json
    if "data" in response_json and isinstance(response_json["data"], dict):
        nested = response_json["data"]
        return nested.get("item") or nested
    return response_json.get("item") or response_json


def test_vote_solution_and_notifications(client):
    author_headers = _auth_register_and_login(client, email="author_vote@example.com")
    problem = _create_problem(
        client,
        author_headers,
        title="Voting",
        description="Vote on my answer",
        problem_type="technical",
    )

    # Author posts a solution
    r_solution = client.post(
        f"/problems/{problem['id']}/solutions",
        headers=author_headers,
        json={"content": "Detailed solution"},
    )
    assert r_solution.status_code in (200, 201), r_solution.data
    solution_payload = _extract_item(r_solution.get_json())
    solution_id = solution_payload.get("id")
    assert solution_id, f"Unexpected solution payload: {solution_payload}"

    voter_headers = _auth_register_and_login(client, email="voter@example.com")

    # Upvote the solution
    r_upvote = client.post(
        f"/solutions/{solution_id}/vote",
        headers=voter_headers,
        json={"vote_type": "up"},
    )
    assert r_upvote.status_code == 200, r_upvote.data
    upvote_payload = _extract_item(r_upvote.get_json())
    assert upvote_payload.get("id") == solution_id
    assert upvote_payload.get("votes", 0) >= 1
    assert upvote_payload.get("my_vote", upvote_payload.get("user_vote")) == 1

    # Author should receive a vote notification
    r_notifications = client.get("/notifications", headers=author_headers)
    assert r_notifications.status_code == 200, r_notifications.data
    notifications_body = r_notifications.get_json()
    notifications_list = notifications_body.get("notifications") or notifications_body.get("items") or []
    assert isinstance(notifications_list, list)
    assert any(n.get("type") == "vote" for n in notifications_list), notifications_list

    # Removing the vote should zero out the user's vote flag
    r_remove = client.delete(f"/solutions/{solution_id}/vote", headers=voter_headers)
    assert r_remove.status_code == 200, r_remove.data
    remove_payload = _extract_item(r_remove.get_json())
    assert remove_payload.get("my_vote", remove_payload.get("user_vote", 0)) == 0


def test_tags_list_structure(client):
    # Ensure at least one tag exists
    r_create = client.post("/tags", json={"name": "flask"})
    assert r_create.status_code in (200, 201), r_create.data
    tag_body = r_create.get_json()
    assert isinstance(tag_body.get("tag"), dict), tag_body

    r_list = client.get("/tags")
    assert r_list.status_code == 200, r_list.data
    tags_body = r_list.get_json()
    items = tags_body.get("items")
    tags_alias = tags_body.get("tags")
    meta = tags_body.get("meta")

    assert isinstance(items, list)
    assert isinstance(tags_alias, list)
    assert tags_alias == items
    assert isinstance(meta, dict)
    assert meta.get("total") == tags_body.get("total")
