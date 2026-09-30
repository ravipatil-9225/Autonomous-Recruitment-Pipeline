"""
Resume Ingestion & GDPR Tests (§11.2)
────────────────────────────────────────
"""
import uuid
from unittest.mock import patch, MagicMock
import pytest
from httpx import AsyncClient
import backend.app.tasks.resume_tasks  # ensure module is loaded for mock patching


@pytest.mark.asyncio
async def test_upload_single_resume(async_client: AsyncClient, recruiter_headers):
    headers = {"Authorization": recruiter_headers["Authorization"]}

    # Create dummy PDF bytes
    file_content = b"%PDF-1.4 sample pdf content for resume parsing test"
    files = {"file": ("resume.pdf", file_content, "application/pdf")}

    mock_task = MagicMock()
    mock_task.id = "task-123"

    with patch("backend.app.services.storage_service.upload_resume", return_value="resumes/test-uuid.pdf"), \
         patch("backend.app.tasks.resume_tasks.parse_resume_task.delay", return_value=mock_task):

        response = await async_client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers=headers,
        )

    assert response.status_code == 202
    data = response.json()
    assert "resume_id" in data
    assert "candidate_id" in data
    assert data["parse_task_id"] == "task-123"


@pytest.mark.asyncio
async def test_upload_invalid_file_type(async_client: AsyncClient, recruiter_headers):
    headers = {"Authorization": recruiter_headers["Authorization"]}
    file_content = b"executable code or malware"
    files = {"file": ("malicious.exe", file_content, "application/octet-stream")}

    response = await async_client.post(
        "/api/v1/resumes/upload",
        files=files,
        headers=headers,
    )
    assert response.status_code in (400, 415)


@pytest.mark.asyncio
async def test_gdpr_deletion_admin(async_client: AsyncClient, admin_headers, recruiter_headers):
    # First upload a resume as recruiter
    file_content = b"%PDF-1.4 candidate resume"
    files = {"file": ("cand.pdf", file_content, "application/pdf")}

    mock_task = MagicMock()
    mock_task.id = "task-456"

    with patch("backend.app.services.storage_service.upload_resume", return_value="resumes/cand.pdf"), \
         patch("backend.app.tasks.resume_tasks.parse_resume_task.delay", return_value=mock_task):

        upload_resp = await async_client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers={"Authorization": recruiter_headers["Authorization"]},
        )
    
    cand_id = upload_resp.json()["candidate_id"]

    # Delete as admin
    with patch("backend.app.services.storage_service.delete_resume", return_value=True):
        del_resp = await async_client.delete(
            f"/api/v1/resumes/candidate/{cand_id}",
            headers={"Authorization": admin_headers["Authorization"]},
        )

    assert del_resp.status_code == 200
    assert del_resp.json()["pii_wiped"] is True

