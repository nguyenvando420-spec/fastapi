"""
Test Suite: Domain Version Management
Tham khảo HashiCorp Vault Key Versioning & AWS KMS Key Rotation.

Tests cover:
1. Tạo domain → version tự động v1, status active
2. Rotate domain → v2, v1 → rotated
3. Rotate nhiều lần → v3, v4...
4. Tokenize tự động dùng version mới nhất
5. Detokenize tìm được token từ version cũ (cross-version lookup)
6. Deprecate version → chặn detokenize
7. Edge cases: rotate domain không tồn tại, deprecate version active
8. Version history API
"""

import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.admin import System, Domain
from app.models.rbac import User
from sqlalchemy import text


# ══════════════════════════════════════════════════════════════════════════════
#  Helper: tạo System + Schema sẵn trên cả Admin DB lẫn Token DB
# ══════════════════════════════════════════════════════════════════════════════

async def _create_system(db_session, token_db_session, name: str) -> System:
    """Tạo System trên Admin DB + Schema vật lý trên Token DB."""
    system = System(name=name, description=f"test system {name}")
    db_session.add(system)
    await db_session.flush()
    await token_db_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{name}"'))
    await token_db_session.commit()
    return system


# ══════════════════════════════════════════════════════════════════════════════
#  1. Tạo Domain → Version tự động v1
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_domain_auto_version_v1(override_get_db, db_session, token_db_session, auth_token):
    """Khi tạo domain mới, version_number=1, version='v1', status='active', tạo bảng vật lý."""
    system = await _create_system(db_session, token_db_session, f"sys_v1_{uuid.uuid4().hex[:6]}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": "credit_card",
            "system_id": str(system.id),
            "description": "PCI domain"
        })

        assert resp.status_code == 201, f"Unexpected: {resp.json()}"
        data = resp.json()
        assert data["version"] == "v1"
        assert data["version_number"] == 1
        assert data["status"] == "active"
        assert data["name"] == "credit_card"


# ══════════════════════════════════════════════════════════════════════════════
#  2. Rotate Domain → v2, v1 → rotated
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rotate_domain_v1_to_v2(override_get_db, db_session, token_db_session, auth_token):
    """Rotate domain: v1→rotated, tạo v2→active."""
    system = await _create_system(db_session, token_db_session, f"sys_rot_{uuid.uuid4().hex[:6]}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Tạo domain
        create_resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": "phone_number",
            "system_id": str(system.id),
        })
        assert create_resp.status_code == 201
        domain_id = create_resp.json()["id"]

        # Rotate
        rotate_resp = await ac.post(f"/api/v1/admin/domains/{domain_id}/rotate", headers=headers)
        assert rotate_resp.status_code == 201, f"Rotate failed: {rotate_resp.json()}"
        rotate_data = rotate_resp.json()

        # Check new version
        assert rotate_data["new_version"]["version"] == "v2"
        assert rotate_data["new_version"]["version_number"] == 2
        assert rotate_data["new_version"]["status"] == "active"

        # Check old version
        assert rotate_data["previous_version"]["version"] == "v1"
        assert rotate_data["previous_version"]["status"] == "rotated"

        assert "đã rotate" in rotate_data["message"]


# ══════════════════════════════════════════════════════════════════════════════
#  3. Rotate nhiều lần → v3, v4...
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rotate_multiple_times(override_get_db, db_session, token_db_session, auth_token):
    """Rotate 3 lần: v1→v2→v3→v4. Chỉ v4 là active."""
    system = await _create_system(db_session, token_db_session, f"sys_multi_{uuid.uuid4().hex[:6]}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Tạo domain v1
        resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": "ssn",
            "system_id": str(system.id),
        })
        domain_id = resp.json()["id"]

        # Rotate 3 lần
        for expected_new_ver in [2, 3, 4]:
            # Rotate cần dùng latest domain_id — đầu tiên lấy lại domain_id hiện tại
            rot_resp = await ac.post(f"/api/v1/admin/domains/{domain_id}/rotate", headers=headers)
            assert rot_resp.status_code == 201, f"Rotate to v{expected_new_ver} failed: {rot_resp.json()}"
            rot_data = rot_resp.json()
            assert rot_data["new_version"]["version_number"] == expected_new_ver
            assert rot_data["new_version"]["status"] == "active"
            assert rot_data["previous_version"]["status"] == "rotated"

        # Kiểm tra version history
        history_resp = await ac.get(f"/api/v1/admin/domains/{domain_id}/versions", headers=headers)
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert history["total_versions"] == 4
        # Versions sắp xếp từ mới nhất
        assert history["versions"][0]["version_number"] == 4
        assert history["versions"][0]["status"] == "active"
        assert history["versions"][-1]["version_number"] == 1
        assert history["versions"][-1]["status"] == "rotated"


# ══════════════════════════════════════════════════════════════════════════════
#  4. Tokenize tự động dùng version mới nhất
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_tokenize_uses_latest_version(override_get_db, db_session, token_db_session, auth_token):
    """Tokenize phải dùng version active mới nhất sau rotate."""
    uid = uuid.uuid4().hex[:6]
    system = await _create_system(db_session, token_db_session, f"sys_tok_{uid}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Tạo domain v1
        resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": f"tok_dom_{uid}",
            "system_id": str(system.id),
        })
        assert resp.status_code == 201
        domain_id = resp.json()["id"]

        # Tokenize trên v1
        tok_v1_resp = await ac.post("/api/v1/tokens/tokenize", headers=headers, json={
            "system_name": system.name,
            "domain_name": f"tok_dom_{uid}",
            "data": ["secret_v1"]
        })
        assert tok_v1_resp.status_code == 201
        token_v1 = list(tok_v1_resp.json()["results"].values())[0]
        # Token format: system:domain:version:hmac
        assert ":v1:" in token_v1

        # Rotate → v2
        rot_resp = await ac.post(f"/api/v1/admin/domains/{domain_id}/rotate", headers=headers)
        assert rot_resp.status_code == 201

        # Tokenize trên v2 (tự động)
        tok_v2_resp = await ac.post("/api/v1/tokens/tokenize", headers=headers, json={
            "system_name": system.name,
            "domain_name": f"tok_dom_{uid}",
            "data": ["secret_v2"]
        })
        assert tok_v2_resp.status_code == 201
        token_v2 = list(tok_v2_resp.json()["results"].values())[0]
        # Token mới phải có version v2
        assert ":v2:" in token_v2


# ══════════════════════════════════════════════════════════════════════════════
#  5. Detokenize tìm được token từ version cũ (cross-version)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_detokenize_cross_version(override_get_db, db_session, token_db_session, auth_token):
    """Detokenize phải tìm được token từ v1 sau khi đã rotate lên v2."""
    uid = uuid.uuid4().hex[:6]
    system = await _create_system(db_session, token_db_session, f"sys_xver_{uid}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Tạo domain v1
        resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": f"xver_dom_{uid}",
            "system_id": str(system.id),
        })
        domain_id = resp.json()["id"]

        # Tokenize trên v1
        tok_resp = await ac.post("/api/v1/tokens/tokenize", headers=headers, json={
            "system_name": system.name,
            "domain_name": f"xver_dom_{uid}",
            "data": ["old_secret"]
        })
        token_v1 = list(tok_resp.json()["results"].values())[0]

        # Rotate → v2
        await ac.post(f"/api/v1/admin/domains/{domain_id}/rotate", headers=headers)

        # Detokenize token v1 (sau khi đã rotate)
        detok_resp = await ac.post("/api/v1/tokens/detokenize", headers=headers, json={
            "system_name": system.name,
            "domain_name": f"xver_dom_{uid}",
            "tokens": [token_v1]
        })
        assert detok_resp.status_code == 200
        detok_data = detok_resp.json()
        assert detok_data["results"][token_v1] == "old_secret"
        assert len(detok_data["missing_tokens"]) == 0


# ══════════════════════════════════════════════════════════════════════════════
#  6. Deprecate version → chặn detokenize
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_deprecate_blocks_detokenize(override_get_db, db_session, token_db_session, auth_token):
    """Sau khi deprecate v1, detokenize không tìm thấy token v1 nữa."""
    uid = uuid.uuid4().hex[:6]
    system = await _create_system(db_session, token_db_session, f"sys_dep_{uid}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Tạo domain v1 + Tokenize
        resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": f"dep_dom_{uid}",
            "system_id": str(system.id),
        })
        domain_id = resp.json()["id"]

        tok_resp = await ac.post("/api/v1/tokens/tokenize", headers=headers, json={
            "system_name": system.name,
            "domain_name": f"dep_dom_{uid}",
            "data": ["deprecated_secret"]
        })
        token_v1 = list(tok_resp.json()["results"].values())[0]

        # Rotate → v2 (v1 → rotated)
        await ac.post(f"/api/v1/admin/domains/{domain_id}/rotate", headers=headers)

        # Deprecate v1
        dep_resp = await ac.patch(
            f"/api/v1/admin/domains/{domain_id}/versions/1/deprecate",
            headers=headers
        )
        assert dep_resp.status_code == 200
        assert dep_resp.json()["status"] == "deprecated"

        # Detokenize token v1 → should be missing (deprecated)
        detok_resp = await ac.post("/api/v1/tokens/detokenize", headers=headers, json={
            "system_name": system.name,
            "domain_name": f"dep_dom_{uid}",
            "tokens": [token_v1]
        })
        assert detok_resp.status_code == 200
        detok_data = detok_resp.json()
        assert token_v1 in detok_data["missing_tokens"]
        assert detok_data["results"][token_v1] is None


# ══════════════════════════════════════════════════════════════════════════════
#  7. Edge Cases
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rotate_nonexistent_domain(override_get_db, auth_token):
    """Rotate domain không tồn tại → 404."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    fake_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/v1/admin/domains/{fake_id}/rotate", headers=headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deprecate_active_version_fails(override_get_db, db_session, token_db_session, auth_token):
    """Không thể deprecate version đang active — phải rotate trước."""
    uid = uuid.uuid4().hex[:6]
    system = await _create_system(db_session, token_db_session, f"sys_depact_{uid}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": f"depact_dom_{uid}",
            "system_id": str(system.id),
        })
        domain_id = resp.json()["id"]

        # Try to deprecate active v1 → should fail
        dep_resp = await ac.patch(
            f"/api/v1/admin/domains/{domain_id}/versions/1/deprecate",
            headers=headers
        )
        assert dep_resp.status_code == 400
        assert "active" in dep_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deprecate_nonexistent_version(override_get_db, db_session, token_db_session, auth_token):
    """Deprecate version không tồn tại → 404."""
    uid = uuid.uuid4().hex[:6]
    system = await _create_system(db_session, token_db_session, f"sys_depne_{uid}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": f"depne_dom_{uid}",
            "system_id": str(system.id),
        })
        domain_id = resp.json()["id"]

        dep_resp = await ac.patch(
            f"/api/v1/admin/domains/{domain_id}/versions/99/deprecate",
            headers=headers
        )
        assert dep_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_domain_fails(override_get_db, db_session, token_db_session, auth_token):
    """Tạo domain trùng tên trong cùng system → 400."""
    uid = uuid.uuid4().hex[:6]
    system = await _create_system(db_session, token_db_session, f"sys_dup_{uid}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Lần 1 OK
        resp1 = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": f"dup_dom_{uid}",
            "system_id": str(system.id),
        })
        assert resp1.status_code == 201

        # Lần 2 trùng → 400
        resp2 = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": f"dup_dom_{uid}",
            "system_id": str(system.id),
        })
        assert resp2.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
#  8. Version History API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_version_history_api(override_get_db, db_session, token_db_session, auth_token):
    """GET /domains/{id}/versions trả đúng danh sách version."""
    uid = uuid.uuid4().hex[:6]
    system = await _create_system(db_session, token_db_session, f"sys_hist_{uid}")
    await db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Tạo domain + rotate 1 lần
        resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": f"hist_dom_{uid}",
            "system_id": str(system.id),
        })
        domain_id = resp.json()["id"]
        await ac.post(f"/api/v1/admin/domains/{domain_id}/rotate", headers=headers)

        # Lấy version history
        hist_resp = await ac.get(f"/api/v1/admin/domains/{domain_id}/versions", headers=headers)
        assert hist_resp.status_code == 200
        hist = hist_resp.json()

        assert hist["domain_name"] == f"hist_dom_{uid}"
        assert hist["system_name"] == system.name
        assert hist["total_versions"] == 2
        assert len(hist["versions"]) == 2
        # Mới nhất trước
        assert hist["versions"][0]["version_number"] == 2
        assert hist["versions"][0]["status"] == "active"
        assert hist["versions"][1]["version_number"] == 1
        assert hist["versions"][1]["status"] == "rotated"
