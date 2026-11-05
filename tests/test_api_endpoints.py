"""Integration tests for all FastAPI endpoints."""

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_api_health():
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["videos_indexed"] >= 8
        assert data["dsa_problems_indexed"] >= 300


def test_api_dsa_snippet():
    with TestClient(app) as client:
        res = client.get("/api/dsa-snippet?q=kadane")
        assert res.status_code == 200
        data = res.json()
        assert data["found"] is True
        assert "Kadane" in data["problem"]["title"]
        assert "maxSubArray" in data["problem"]["code_cpp"]
        assert data["problem"]["code_python"] != ""


def test_api_validate_key_endpoint():
    with TestClient(app) as client:
        # Invalid key should return valid: False gracefully
        res = client.post("/api/validate-key", json={"provider": "groq", "api_key": "bad_key_123"})
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert "error" in data


def test_api_search_with_dsa_snippet():
    with TestClient(app) as client:
        res = client.get("/api/search?q=two+sum")
        assert res.status_code == 200
        data = res.json()
        assert data["total_found"] > 0
        assert data["dsa_snippet"] is not None
        assert "2 Sum" in data["dsa_snippet"]["title"]


def test_api_answer_extractive_fallback():
    with TestClient(app) as client:
        res = client.post("/api/answer", json={"query": "two sum", "provider": "extractive"})
        assert res.status_code == 200
        data = res.json()
        assert len(data["bullets"]) > 0
        assert data["provider"] == "extractive"
        assert data["dsa_snippet"] is not None


def test_api_execute_code_endpoint():
    with TestClient(app) as client:
        res = client.post(
            "/api/execute",
            json={
                "language": "python",
                "code": "print('Runner Test: 42')",
                "stdin_input": "",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "Runner Test: 42" in data["stdout"]
        assert data["exit_code"] == 0


def test_api_edge_cases_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/edge-cases?topic=array&title=kadane")
        assert res.status_code == 200
        data = res.json()
        assert len(data["cases"]) > 0
        assert any("Negative" in c["name"] for c in data["cases"])


def test_api_grill_me_generate_and_eval():
    with TestClient(app) as client:
        # 1. Generate interview challenge question
        res_q = client.post(
            "/api/grill-me",
            json={
                "title": "3Sum Problem",
                "topic": "Arrays",
                "code": "def threeSum(nums): pass",
            },
        )
        assert res_q.status_code == 200
        q_data = res_q.json()
        assert q_data["mode"] == "question"
        assert len(q_data["question"]) > 10
        assert "duplicate" in q_data["trap_warning"].lower()

        # 2. Submit student answer for evaluation
        res_eval = client.post(
            "/api/grill-me",
            json={
                "title": "3Sum Problem",
                "topic": "Arrays",
                "question": q_data["question"],
                "trap_warning": q_data["trap_warning"],
                "gold_standard": q_data["gold_standard"],
                "user_answer": "We sort the array first, and then while left < right we advance left++ and right-- to skip all duplicate consecutive elements.",
            },
        )
        assert res_eval.status_code == 200
        eval_data = res_eval.json()
        assert eval_data["mode"] == "evaluation"
        assert eval_data["evaluation"]["score"] >= 7
        assert eval_data["evaluation"]["verdict"] in ("Outstanding", "Strong", "Partially Correct")


def test_api_syntax_query_expansion():
    with TestClient(app) as client:
        # Code syntax query gets expanded to pedagogical concepts and retrieves relevant lecture
        res = client.get("/api/search?q=why+nums%5Bleft%5D+%3D%3D+nums%5Bleft-1%5D")
        assert res.status_code == 200
        data = res.json()
        assert data["total_found"] > 0
        # Results should be found and refined
        assert len(data["results"]) > 0
        assert data["results"][0]["seek_sec"] >= 0


def test_api_roadmap_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/roadmap")
        assert res.status_code == 200
        data = res.json()
        assert data["total_problems"] >= 300
        assert len(data["topics"]) >= 15
        first_topic = data["topics"][0]
        assert "name" in first_topic
        assert "icon" in first_topic
        assert "subtopics" in first_topic
        assert len(first_topic["subtopics"]) > 0
        first_prob = first_topic["subtopics"][0]["problems"][0]
        assert "id" in first_prob
        assert "title" in first_prob
        assert "difficulty" in first_prob

