# =============================================================================
# tests/test_assets.py — Asset CRUD, Pagination, Sorting, Filtering
# =============================================================================

import pytest
from tests.conftest import make_asset_payload


# =============================================================================
# CRUD — Create / Read / Update / Delete
# =============================================================================

class TestAssetCRUD:

    def test_create_asset_returns_201(self, client, editor_token):
        """POST /assets/ with valid payload returns 201 and the created asset."""
        payload = make_asset_payload(type="domain", value="crud-test.com", source="unit_test")
        r = client.post("/assets/", json=payload, headers={"Authorization": f"Bearer {editor_token}"})
        assert r.status_code == 201
        data = r.json()
        assert data["type"] == "domain"
        assert data["value"] == "crud-test.com"
        assert "id" in data
        assert data["status"] == "active"

    def test_create_asset_response_uses_metadata_alias(self, client, editor_token):
        """Response JSON must expose 'metadata' key (serialization_alias), never 'asset_metadata'."""
        payload = make_asset_payload(value="alias-check.com", metadata={"env": "prod"})
        r = client.post("/assets/", json=payload, headers={"Authorization": f"Bearer {editor_token}"})
        assert r.status_code == 201
        data = r.json()
        assert "metadata" in data, "Response must use 'metadata' serialization alias"
        assert "asset_metadata" not in data, "'asset_metadata' must not appear in API response"
        assert data["metadata"] == {"env": "prod"}

    def test_create_asset_accepts_asset_metadata_key(self, client, editor_token):
        """The 'asset_metadata' field name is also accepted on input (populate_by_name=True)."""
        payload = {
            "type": "domain",
            "value": "field-name-key.com",
            "source": "test",
            "asset_metadata": {"legacy": True},
        }
        r = client.post("/assets/", json=payload, headers={"Authorization": f"Bearer {editor_token}"})
        assert r.status_code == 201
        assert r.json()["metadata"] == {"legacy": True}

    def test_read_single_asset_by_id(self, client, editor_token):
        """GET /assets/{id} returns the correct asset."""
        payload = make_asset_payload(value="read-by-id.com")
        create_r = client.post("/assets/", json=payload, headers={"Authorization": f"Bearer {editor_token}"})
        asset_id = create_r.json()["id"]

        r = client.get(f"/assets/{asset_id}")
        assert r.status_code == 200
        assert r.json()["id"] == asset_id

    def test_read_single_asset_not_found(self, client):
        """GET /assets/{id} with a non-existent ID returns 404."""
        r = client.get("/assets/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_update_asset_patch(self, client, editor_token):
        """PATCH /assets/{id} updates only the provided fields."""
        payload = make_asset_payload(value="patch-target.com", tags=["initial"])
        asset_id = client.post(
            "/assets/", json=payload, headers={"Authorization": f"Bearer {editor_token}"}
        ).json()["id"]

        patch = {"status": "stale", "tags": ["updated"]}
        r = client.patch(
            f"/assets/{asset_id}", json=patch,
            headers={"Authorization": f"Bearer {editor_token}"}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "stale"
        assert data["tags"] == ["updated"]
        assert data["value"] == "patch-target.com"  # Unchanged field preserved

    def test_update_asset_accepts_metadata_alias(self, client, editor_token):
        """PATCH with 'metadata' key correctly updates asset_metadata via alias."""
        asset_id = client.post(
            "/assets/",
            json=make_asset_payload(value="meta-patch.com"),
            headers={"Authorization": f"Bearer {editor_token}"},
        ).json()["id"]

        r = client.patch(
            f"/assets/{asset_id}",
            json={"metadata": {"patched": True}},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert r.status_code == 200
        assert r.json()["metadata"] == {"patched": True}

    def test_delete_asset_admin_only(self, client, admin_token, editor_token):
        """DELETE /assets/{id} requires admin role; editor receives 403."""
        asset_id = client.post(
            "/assets/",
            json=make_asset_payload(value="delete-me.com"),
            headers={"Authorization": f"Bearer {editor_token}"},
        ).json()["id"]

        # Editor → 403
        r = client.delete(f"/assets/{asset_id}", headers={"Authorization": f"Bearer {editor_token}"})
        assert r.status_code == 403

        # Admin → 204
        r = client.delete(f"/assets/{asset_id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 204

        # Verify it's gone
        r = client.get(f"/assets/{asset_id}")
        assert r.status_code == 404

    def test_create_without_auth_returns_401(self, client):
        """Unauthenticated POST to /assets/ must return 401."""
        r = client.post("/assets/", json=make_asset_payload())
        assert r.status_code == 401

    def test_viewer_cannot_create_asset(self, client, viewer_token):
        """Viewer role must receive 403 when attempting asset creation."""
        r = client.post(
            "/assets/",
            json=make_asset_payload(value="viewer-attempt.com"),
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 403


# =============================================================================
# Idempotency — same (type, value) merges, not duplicates
# =============================================================================

class TestAssetIdempotency:

    def test_duplicate_create_returns_merged_asset(self, client, editor_token):
        """POSTing the same (type, value) twice merges into a single record."""
        headers = {"Authorization": f"Bearer {editor_token}"}
        payload = make_asset_payload(value="idempotent.com", tags=["first"])
        client.post("/assets/", json=payload, headers=headers)

        # Second create — different tag, should merge
        payload2 = make_asset_payload(value="idempotent.com", tags=["second"])
        r = client.post("/assets/", json=payload2, headers=headers)
        assert r.status_code == 201

        # Listing should return exactly 1 asset
        listing = client.get("/assets/").json()
        domain_assets = [a for a in listing if a["value"] == "idempotent.com"]
        assert len(domain_assets) == 1
        # Both tags should be present after union merge
        assert set(domain_assets[0]["tags"]) == {"first", "second"}


# =============================================================================
# Pagination
# =============================================================================

class TestPagination:

    def _seed_n_assets(self, client, editor_token, n: int):
        headers = {"Authorization": f"Bearer {editor_token}"}
        for i in range(n):
            client.post(
                "/assets/",
                json=make_asset_payload(value=f"page-asset-{i}.com", source=f"seed_{i}"),
                headers=headers,
            )

    def test_pagination_page_size(self, client, editor_token):
        """size parameter correctly limits the number of returned results."""
        self._seed_n_assets(client, editor_token, 15)
        r = client.get("/assets/?page=1&size=5")
        assert r.status_code == 200
        assert len(r.json()) == 5

    def test_pagination_page_2(self, client, editor_token):
        """page=2 returns the second window of results."""
        self._seed_n_assets(client, editor_token, 10)
        page1 = client.get("/assets/?page=1&size=5").json()
        page2 = client.get("/assets/?page=2&size=5").json()
        ids_p1 = {a["id"] for a in page1}
        ids_p2 = {a["id"] for a in page2}
        assert len(ids_p2) == 5
        assert ids_p1.isdisjoint(ids_p2), "Pages must not overlap"

    def test_pagination_beyond_end_returns_empty(self, client, editor_token):
        """Requesting a page beyond the dataset returns an empty list."""
        self._seed_n_assets(client, editor_token, 3)
        r = client.get("/assets/?page=100&size=20")
        assert r.status_code == 200
        assert r.json() == []


# =============================================================================
# Filtering
# =============================================================================

class TestFiltering:

    def test_filter_by_type(self, client, editor_token):
        """type filter returns only assets of the specified type."""
        headers = {"Authorization": f"Bearer {editor_token}"}
        client.post("/assets/", json=make_asset_payload(type="domain", value="filter-domain.com"), headers=headers)
        client.post("/assets/", json=make_asset_payload(type="ip_address", value="1.2.3.4"), headers=headers)

        r = client.get("/assets/?type=domain")
        assert r.status_code == 200
        results = r.json()
        assert all(a["type"] == "domain" for a in results)

    def test_filter_by_status(self, client, editor_token, admin_token):
        """status filter returns only assets matching the given lifecycle state."""
        headers_editor = {"Authorization": f"Bearer {editor_token}"}
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        # Create two assets, mark one stale
        asset_id = client.post(
            "/assets/", json=make_asset_payload(value="active-asset.com"), headers=headers_editor
        ).json()["id"]
        client.post("/assets/", json=make_asset_payload(value="another-active.com"), headers=headers_editor)

        client.patch(f"/assets/{asset_id}", json={"status": "stale"}, headers=headers_editor)

        stale_results = client.get("/assets/?status=stale").json()
        active_results = client.get("/assets/?status=active").json()
        assert all(a["status"] == "stale" for a in stale_results)
        assert all(a["status"] == "active" for a in active_results)

    def test_filter_by_tag(self, client, editor_token):
        """tag filter returns only assets that contain the specified tag."""
        headers = {"Authorization": f"Bearer {editor_token}"}
        client.post("/assets/", json=make_asset_payload(value="tagged.com", tags=["prod", "critical"]), headers=headers)
        client.post("/assets/", json=make_asset_payload(value="untagged.com", tags=[]), headers=headers)

        r = client.get("/assets/?tag=prod")
        assert r.status_code == 200
        results = r.json()
        assert len(results) >= 1
        assert all("prod" in a["tags"] for a in results)

    def test_filter_by_value_contains(self, client, editor_token):
        """value_contains performs case-insensitive substring matching."""
        headers = {"Authorization": f"Bearer {editor_token}"}
        client.post("/assets/", json=make_asset_payload(value="api.example.com"), headers=headers)
        client.post("/assets/", json=make_asset_payload(value="blog.example.com"), headers=headers)
        client.post("/assets/", json=make_asset_payload(value="other-domain.net"), headers=headers)

        r = client.get("/assets/?value_contains=example")
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 2
        assert all("example" in a["value"] for a in results)

    def test_combined_filters(self, client, editor_token):
        """Multiple filters are applied conjunctively (AND logic)."""
        headers = {"Authorization": f"Bearer {editor_token}"}
        client.post(
            "/assets/",
            json=make_asset_payload(type="subdomain", value="api.target.com", tags=["scan"]),
            headers=headers,
        )
        client.post(
            "/assets/",
            json=make_asset_payload(type="domain", value="target.com", tags=["scan"]),
            headers=headers,
        )

        r = client.get("/assets/?type=subdomain&tag=scan&value_contains=api")
        results = r.json()
        assert len(results) == 1
        assert results[0]["value"] == "api.target.com"


# =============================================================================
# Sorting
# =============================================================================

class TestSorting:

    def test_sort_by_value_asc(self, client, editor_token):
        """sort_by=value&sort_order=asc returns assets in alphabetical order."""
        headers = {"Authorization": f"Bearer {editor_token}"}
        for v in ["zebra.com", "apple.com", "mango.com"]:
            client.post("/assets/", json=make_asset_payload(value=v), headers=headers)

        r = client.get("/assets/?sort_by=value&sort_order=asc")
        values = [a["value"] for a in r.json()]
        assert values == sorted(values)

    def test_sort_by_value_desc(self, client, editor_token):
        """sort_by=value&sort_order=desc returns assets in reverse alphabetical order."""
        headers = {"Authorization": f"Bearer {editor_token}"}
        for v in ["zebra.com", "apple.com", "mango.com"]:
            client.post("/assets/", json=make_asset_payload(value=v), headers=headers)

        r = client.get("/assets/?sort_by=value&sort_order=desc")
        values = [a["value"] for a in r.json()]
        assert values == sorted(values, reverse=True)
