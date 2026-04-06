"""
Tests for the file upload endpoint (Phase 0: validation, encoding, DB persistence).
"""
import io


def test_upload_csv(client, project, csv_bytes, auth_headers):
    pid = project["id"]
    r = client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(pid)},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "data.csv"
    assert body["size_bytes"] > 0
    assert "file_hash" in body


def test_upload_sets_project_ready(client, project, csv_bytes, auth_headers):
    pid = project["id"]
    client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(pid)},
        headers=auth_headers,
    )
    r = client.get(f"/projects/{pid}", headers=auth_headers)
    assert r.json()["status"] == "ready"


def test_upload_stats_count(client, project, csv_bytes, auth_headers):
    pid = project["id"]
    client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"project_id": str(pid)},
        headers=auth_headers,
    )
    stats = client.get("/projects/stats", headers=auth_headers).json()
    assert stats["total_files"] == 1


def test_upload_invalid_extension(client, project, auth_headers):
    pid = project["id"]
    r = client.post(
        "/upload",
        files={"file": ("report.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
        data={"project_id": str(pid)},
        headers=auth_headers,
    )
    assert r.status_code == 415
    assert "extension" in r.text.lower() or "pdf" in r.text.lower()


def test_upload_wrong_project(client, auth_headers):
    """Uploading to a non-existent project should fail."""
    r = client.post(
        "/upload",
        files={"file": ("data.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")},
        data={"project_id": "99999"},
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_upload_latin1_csv(client, project, auth_headers):
    """CSV with latin-1 encoding should be accepted."""
    pid = project["id"]
    content = "name,city\nJos\xe9,M\xe9xico\nMar\xeda,Bogot\xe1\n" * 5
    raw = content.encode("latin-1")
    r = client.post(
        "/upload",
        files={"file": ("latin.csv", io.BytesIO(raw), "text/csv")},
        data={"project_id": str(pid)},
        headers=auth_headers,
    )
    assert r.status_code == 200


def test_upload_xlsx(client, project, auth_headers):
    """An xlsx file should be accepted (not rejected as unknown extension)."""
    import openpyxl
    import io as _io
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "score"])
    for i in range(10):
        ws.append([f"user_{i}", i * 10])
    buf = _io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    pid = project["id"]
    r = client.post(
        "/upload",
        files={"file": ("sheet.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"project_id": str(pid)},
        headers=auth_headers,
    )
    assert r.status_code == 200
