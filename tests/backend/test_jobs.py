"""
Job Management API Tests (§11.1)
───────────────────────────────────
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_job(async_client: AsyncClient, recruiter_headers):
    headers = {"Authorization": recruiter_headers["Authorization"]}
    
    # 1. Create job
    create_payload = {
        "title": "Senior AI Engineer",
        "raw_jd_text": "We are seeking a Senior AI Engineer with Python, LangChain, FastAPI expertise.",
        "department": "Engineering",
        "location": "Remote",
    }
    create_resp = await async_client.post("/api/v1/jobs", json=create_payload, headers=headers)
    assert create_resp.status_code == 201
    job_data = create_resp.json()
    assert job_data["title"] == "Senior AI Engineer"
    assert job_data["status"] == "draft"
    job_id = job_data["id"]

    # 2. Get job
    get_resp = await async_client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id


@pytest.mark.asyncio
async def test_job_lifecycle_state_transitions(
    async_client: AsyncClient, recruiter_headers, hiring_manager_headers
):
    r_headers = {"Authorization": recruiter_headers["Authorization"]}
    hm_headers = {"Authorization": hiring_manager_headers["Authorization"]}

    # Create draft job
    create_resp = await async_client.post(
        "/api/v1/jobs",
        json={
            "title": "Data Scientist",
            "raw_jd_text": "Machine Learning and Python experience required for building end-to-end data science pipelines.",
        },
        headers=r_headers,
    )
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # Publish draft -> open
    pub_resp = await async_client.post(f"/api/v1/jobs/{job_id}/publish", headers=r_headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "open"

    # Close open -> closed (Hiring Manager)
    close_resp = await async_client.post(f"/api/v1/jobs/{job_id}/close", headers=hm_headers)
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_list_jobs(async_client: AsyncClient, recruiter_headers):
    headers = {"Authorization": recruiter_headers["Authorization"]}

    for title in ["Job A", "Job B"]:
        resp = await async_client.post(
            "/api/v1/jobs",
            json={
                "title": title,
                "raw_jd_text": f"Requirements and detailed specifications for role {title} in software engineering.",
            },
            headers=headers,
        )
        assert resp.status_code == 201

    list_resp = await async_client.get("/api/v1/jobs", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

