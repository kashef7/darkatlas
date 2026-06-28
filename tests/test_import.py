# =============================================================================
# tests/test_import.py — Savepoint Batch Processing, Deep Merge, Lifecycle
# =============================================================================

import pytest
from tests.conftest import make_asset_payload


# =============================================================================
# Happy Path — Clean Batch Import
# =============================================================================

class TestBulkImportHappyPath:

    def test_bulk_import_creates_all_valid_assets(self, client, admin_token):
        """A clean batch of valid assets returns correct created count and no failures."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = [
            make_asset_payload(type="domain", value="bulk-one.com"),
            make_asset_payload(type="domain", value="bulk-two.com"),
            make_asset_payload(type="ip_address", value="192.168.1.1"),
        ]
        r = client.post("/assets/bulk-import", json=payload, headers=headers)
        assert r.status_code == 201
        details = r.json()["details"]
        assert details["created"] == 3
        assert details["updated_merged"] == 0
        assert details["failed"] == []

    def test_bulk_import_requires_admin(self, client, editor_token):
        """Bulk import endpoint enforces admin-only RBAC (editor → 403)."""
        r = client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="unauthorized.com")],
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert r.status_code == 403

    def test_bulk_import_empty_payload_returns_400(self, client, admin_token):
        """An empty list payload is rejected with 400 Bad Request."""
        r = client.post(
            "/assets/bulk-import", json=[],
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 400

    def test_bulk_import_accepts_metadata_alias(self, client, admin_token):
        """Batch items using the 'metadata' key (alias) are correctly processed."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = [
            {
                "type": "subdomain",
                "value": "api.alias-test.com",
                "source": "scanner",
                "metadata": {"scanner": "nmap", "port": 443},
            }
        ]
        r = client.post("/assets/bulk-import", json=payload, headers=headers)
        assert r.status_code == 201
        assert r.json()["details"]["created"] == 1

        # Verify the metadata round-trips correctly
        listing = client.get("/assets/?value_contains=api.alias-test.com").json()
        assert listing[0]["metadata"] == {"scanner": "nmap", "port": 443}


# =============================================================================
# Savepoint Recovery — Corrupt Records
# =============================================================================

class TestSavepointRecovery:

    def test_corrupt_item_does_not_abort_batch(self, client, admin_token):
        """A corrupt item is isolated via savepoint; valid siblings still persist."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = [
            make_asset_payload(type="domain", value="valid-first.com"),       # index 0 — valid
            {"this": "is", "completely": "invalid"},                           # index 1 — corrupt
            make_asset_payload(type="domain", value="valid-third.com"),        # index 2 — valid
        ]
        r = client.post("/assets/bulk-import", json=payload, headers=headers)
        assert r.status_code == 201

        details = r.json()["details"]
        assert details["created"] == 2      # Items 0 and 2 were saved
        assert details["updated_merged"] == 0
        assert len(details["failed"]) == 1  # Item 1 failed

        failed = details["failed"][0]
        assert failed["index"] == 1         # Correct index reported
        assert "message" in failed
        assert "input" in failed

        # Verify the valid assets actually exist in the DB
        listing = client.get("/assets/").json()
        values = {a["value"] for a in listing}
        assert "valid-first.com" in values
        assert "valid-third.com" in values

    def test_multiple_corrupt_items_all_recorded(self, client, admin_token):
        """Every corrupt item in a batch is individually recorded in the failed list."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = [
            {"no_type": "missing"},                                             # index 0
            make_asset_payload(value="only-valid.com"),                        # index 1
            {"type": "INVALID_ENUM_VALUE", "value": "x", "source": "s"},      # index 2
        ]
        r = client.post("/assets/bulk-import", json=payload, headers=headers)
        details = r.json()["details"]

        assert details["created"] == 1
        assert len(details["failed"]) == 2

        failed_indices = {f["index"] for f in details["failed"]}
        assert 0 in failed_indices
        assert 2 in failed_indices

    def test_all_corrupt_batch_returns_zero_created(self, client, admin_token):
        """A batch where every item is invalid results in zero created assets."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = [{"bad": "item"}, {"also": "bad"}]
        r = client.post("/assets/bulk-import", json=payload, headers=headers)
        details = r.json()["details"]
        assert details["created"] == 0
        assert details["updated_merged"] == 0
        assert len(details["failed"]) == 2


# =============================================================================
# Lifecycle Restoration — Stale / Archived → Active on Re-Sighting
# =============================================================================

class TestLifecycleRestoration:

    def test_stale_asset_restored_to_active_on_resight(self, client, editor_token, admin_token):
        """Re-ingesting a stale asset via bulk-import restores its status to active."""
        headers_editor = {"Authorization": f"Bearer {editor_token}"}
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        # 1. Create the asset
        asset_id = client.post(
            "/assets/", json=make_asset_payload(value="stale-target.com"), headers=headers_editor
        ).json()["id"]

        # 2. Mark it as stale
        client.patch(f"/assets/{asset_id}", json={"status": "stale"}, headers=headers_editor)
        assert client.get(f"/assets/{asset_id}").json()["status"] == "stale"

        # 3. Re-ingest via bulk-import — should trigger lifecycle restoration
        r = client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="stale-target.com", source="resight")],
            headers=headers_admin,
        )
        assert r.json()["details"]["updated_merged"] == 1

        # 4. Status must now be active
        refreshed = client.get(f"/assets/{asset_id}").json()
        assert refreshed["status"] == "active"

    def test_archived_asset_restored_to_active_on_resight(self, client, editor_token, admin_token):
        """Re-ingesting an archived asset via bulk-import restores its status to active."""
        headers_editor = {"Authorization": f"Bearer {editor_token}"}
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        asset_id = client.post(
            "/assets/", json=make_asset_payload(value="archived-target.com"), headers=headers_editor
        ).json()["id"]
        client.patch(f"/assets/{asset_id}", json={"status": "archived"}, headers=headers_editor)

        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="archived-target.com")],
            headers=headers_admin,
        )
        assert client.get(f"/assets/{asset_id}").json()["status"] == "active"


# =============================================================================
# Tag Union Deduplication
# =============================================================================

class TestTagUnion:

    def test_tag_union_no_duplicates(self, client, admin_token):
        """Re-ingesting an asset accumulates tags as a deduplicated union set."""
        headers = {"Authorization": f"Bearer {admin_token}"}

        payload1 = [make_asset_payload(value="tag-union.com", tags=["alpha", "beta"])]
        payload2 = [make_asset_payload(value="tag-union.com", tags=["beta", "gamma"])]

        client.post("/assets/bulk-import", json=payload1, headers=headers)
        client.post("/assets/bulk-import", json=payload2, headers=headers)

        listing = client.get("/assets/?value_contains=tag-union.com").json()
        assert len(listing) == 1
        final_tags = set(listing[0]["tags"])
        # Union: alpha, beta, gamma — no duplicates
        assert final_tags == {"alpha", "beta", "gamma"}

    def test_tag_union_with_unique_combination(self, client, admin_token):
        """All unique tags from multiple re-sightings are preserved."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        all_tags = ["t1", "t2", "t3", "t4", "t5"]

        for i, tag in enumerate(all_tags):
            client.post(
                "/assets/bulk-import",
                json=[make_asset_payload(value="accumulate-tags.com", tags=[tag])],
                headers=headers,
            )

        listing = client.get("/assets/?value_contains=accumulate-tags.com").json()
        assert set(listing[0]["tags"]) == set(all_tags)


# =============================================================================
# Deep Metadata Merge
# =============================================================================

class TestDeepMetadataMerge:

    def test_shallow_key_overwrite(self, client, admin_token):
        """Top-level metadata keys from re-sighting overwrite base values."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="merge-shallow.com", metadata={"env": "staging", "version": 1})],
            headers=headers,
        )
        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="merge-shallow.com", metadata={"env": "prod"})],
            headers=headers,
        )

        asset = client.get("/assets/?value_contains=merge-shallow.com").json()[0]
        assert asset["metadata"]["env"] == "prod"      # overwritten
        assert asset["metadata"]["version"] == 1       # preserved from base

    def test_nested_dict_deep_merge(self, client, admin_token):
        """Nested dict values are recursively merged, preserving deep context."""
        headers = {"Authorization": f"Bearer {admin_token}"}

        base_meta = {
            "scan": {
                "tool": "nmap",
                "ports": [80, 443],
                "config": {"timing": "T4", "intensity": "aggressive"},
            }
        }
        incoming_meta = {
            "scan": {
                "ports": [8080],  # overwrite
                "config": {"intensity": "light"},  # partial nested overwrite
                "last_run": "2026-01-01",  # new nested key
            }
        }

        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="deep-merge.com", metadata=base_meta)],
            headers=headers,
        )
        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="deep-merge.com", metadata=incoming_meta)],
            headers=headers,
        )

        asset = client.get("/assets/?value_contains=deep-merge.com").json()[0]
        scan = asset["metadata"]["scan"]

        assert scan["tool"] == "nmap"                       # preserved from base
        assert scan["ports"] == [8080]                      # overwritten by incoming
        assert scan["config"]["timing"] == "T4"             # preserved (deep)
        assert scan["config"]["intensity"] == "light"       # overwritten (deep)
        assert scan["last_run"] == "2026-01-01"             # new key from incoming

    def test_triple_level_deep_merge(self, client, admin_token):
        """Three-level nested merge preserves structure at every depth."""
        headers = {"Authorization": f"Bearer {admin_token}"}

        meta1 = {"a": {"b": {"c": "original", "d": "keep"}}}
        meta2 = {"a": {"b": {"c": "updated"}}}

        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="triple-depth.com", metadata=meta1)],
            headers=headers,
        )
        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="triple-depth.com", metadata=meta2)],
            headers=headers,
        )

        asset = client.get("/assets/?value_contains=triple-depth.com").json()[0]
        nested = asset["metadata"]["a"]["b"]
        assert nested["c"] == "updated"   # overwritten at depth 3
        assert nested["d"] == "keep"      # preserved at depth 3

    def test_metadata_non_dict_value_is_overwritten(self, client, admin_token):
        """When incoming value is not a dict, it fully replaces the base value."""
        headers = {"Authorization": f"Bearer {admin_token}"}

        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="scalar-merge.com", metadata={"count": {"nested": 1}})],
            headers=headers,
        )
        client.post(
            "/assets/bulk-import",
            json=[make_asset_payload(value="scalar-merge.com", metadata={"count": 42})],
            headers=headers,
        )

        asset = client.get("/assets/?value_contains=scalar-merge.com").json()[0]
        # Incoming scalar (42) overwrites the base dict
        assert asset["metadata"]["count"] == 42
