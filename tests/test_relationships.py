# =============================================================================
# tests/test_relationships.py — Directional Graph Constraint Mapping
# =============================================================================
#
# Relationship Rules Matrix (from architectural spec):
#
#   Source Type    → Target Type     Meaning
#   ─────────────────────────────────────────────────────
#   subdomain      → domain          Part of base domain layout
#   service        → ip_address      Network service on specific host
#   ip_address     → subdomain       DNS resolution (bidirectional)
#   subdomain      → ip_address      DNS resolution (bidirectional)
#   certificate    → domain          TLS protection coverage
#   certificate    → subdomain       TLS protection coverage
#   technology     → subdomain       Software framework running on asset
#   technology     → service         Software framework running on service
#
# Any pair NOT in this matrix must return HTTP 400.
# =============================================================================

import pytest
from tests.conftest import make_asset_payload


# =============================================================================
# Helpers
# =============================================================================

def _create_asset(client, editor_token, asset_type: str, value: str) -> str:
    """Creates an asset and returns its ID."""
    r = client.post(
        "/assets/",
        json=make_asset_payload(type=asset_type, value=value),
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 201, f"Asset creation failed: {r.json()}"
    return r.json()["id"]


def _create_relationship(client, editor_token, source_id: str, target_id: str, rel_type: str):
    """Attempts to create a relationship and returns the response."""
    return client.post(
        "/relationships/",
        json={"source_id": source_id, "target_id": target_id, "type": rel_type},
        headers={"Authorization": f"Bearer {editor_token}"},
    )


# =============================================================================
# Valid Relationship Pairs → expect 201
# =============================================================================

class TestValidRelationships:

    def test_subdomain_to_domain(self, client, editor_token):
        """subdomain → domain is a valid relationship (part of base domain layout)."""
        domain_id = _create_asset(client, editor_token, "domain", "valid-domain.com")
        sub_id = _create_asset(client, editor_token, "subdomain", "api.valid-domain.com")
        r = _create_relationship(client, editor_token, sub_id, domain_id, "part_of")
        assert r.status_code == 201
        data = r.json()
        assert data["source_id"] == sub_id
        assert data["target_id"] == domain_id

    def test_service_to_ip_address(self, client, editor_token):
        """service → ip_address is a valid relationship (network service on host)."""
        ip_id = _create_asset(client, editor_token, "ip_address", "10.0.0.1")
        svc_id = _create_asset(client, editor_token, "service", "10.0.0.1:443")
        r = _create_relationship(client, editor_token, svc_id, ip_id, "runs_on")
        assert r.status_code == 201

    def test_ip_address_to_subdomain(self, client, editor_token):
        """ip_address → subdomain is valid (DNS resolution mapping)."""
        sub_id = _create_asset(client, editor_token, "subdomain", "resolve.test.com")
        ip_id = _create_asset(client, editor_token, "ip_address", "10.0.0.2")
        r = _create_relationship(client, editor_token, ip_id, sub_id, "resolves_to")
        assert r.status_code == 201

    def test_subdomain_to_ip_address(self, client, editor_token):
        """subdomain → ip_address is valid (bidirectional resolution)."""
        ip_id = _create_asset(client, editor_token, "ip_address", "10.0.0.3")
        sub_id = _create_asset(client, editor_token, "subdomain", "bi.test.com")
        r = _create_relationship(client, editor_token, sub_id, ip_id, "resolves_to")
        assert r.status_code == 201

    def test_certificate_to_domain(self, client, editor_token):
        """certificate → domain is valid (TLS coverage mapping)."""
        domain_id = _create_asset(client, editor_token, "domain", "tls-domain.com")
        cert_id = _create_asset(client, editor_token, "certificate", "cert:tls-domain.com")
        r = _create_relationship(client, editor_token, cert_id, domain_id, "secures")
        assert r.status_code == 201

    def test_certificate_to_subdomain(self, client, editor_token):
        """certificate → subdomain is valid (wildcard TLS coverage)."""
        sub_id = _create_asset(client, editor_token, "subdomain", "secure.tls-sub.com")
        cert_id = _create_asset(client, editor_token, "certificate", "cert:wildcard.tls-sub.com")
        r = _create_relationship(client, editor_token, cert_id, sub_id, "secures")
        assert r.status_code == 201

    def test_technology_to_subdomain(self, client, editor_token):
        """technology → subdomain is valid (software framework on asset)."""
        sub_id = _create_asset(client, editor_token, "subdomain", "app.tech-test.com")
        tech_id = _create_asset(client, editor_token, "technology", "nginx:1.25")
        r = _create_relationship(client, editor_token, tech_id, sub_id, "runs_on")
        assert r.status_code == 201

    def test_technology_to_service(self, client, editor_token):
        """technology → service is valid (software framework on service)."""
        svc_id = _create_asset(client, editor_token, "service", "10.0.0.4:80")
        tech_id = _create_asset(client, editor_token, "technology", "apache:2.4")
        r = _create_relationship(client, editor_token, tech_id, svc_id, "runs_on")
        assert r.status_code == 201


# =============================================================================
# Invalid Relationship Pairs → expect 400
# =============================================================================

class TestInvalidRelationships:

    def test_domain_to_subdomain_invalid(self, client, editor_token):
        """domain → subdomain is NOT in the rules matrix; must return 400."""
        domain_id = _create_asset(client, editor_token, "domain", "invalid-parent.com")
        sub_id = _create_asset(client, editor_token, "subdomain", "child.invalid-parent.com")
        r = _create_relationship(client, editor_token, domain_id, sub_id, "has_child")
        assert r.status_code == 400

    def test_ip_address_to_service_invalid(self, client, editor_token):
        """ip_address → service is NOT in the rules matrix; must return 400."""
        ip_id = _create_asset(client, editor_token, "ip_address", "10.0.0.5")
        svc_id = _create_asset(client, editor_token, "service", "10.0.0.5:22")
        r = _create_relationship(client, editor_token, ip_id, svc_id, "hosts")
        assert r.status_code == 400

    def test_domain_to_certificate_invalid(self, client, editor_token):
        """domain → certificate is NOT in the rules matrix (reverse of valid direction)."""
        domain_id = _create_asset(client, editor_token, "domain", "reverse-tls.com")
        cert_id = _create_asset(client, editor_token, "certificate", "cert:reverse-tls.com")
        r = _create_relationship(client, editor_token, domain_id, cert_id, "has_cert")
        assert r.status_code == 400

    def test_subdomain_to_subdomain_invalid(self, client, editor_token):
        """subdomain → subdomain self-type pairing is NOT valid."""
        sub1 = _create_asset(client, editor_token, "subdomain", "a.test.com")
        sub2 = _create_asset(client, editor_token, "subdomain", "b.test.com")
        r = _create_relationship(client, editor_token, sub1, sub2, "sibling")
        assert r.status_code == 400

    def test_technology_to_domain_invalid(self, client, editor_token):
        """technology → domain is NOT in the rules matrix."""
        domain_id = _create_asset(client, editor_token, "domain", "tech-to-domain.com")
        tech_id = _create_asset(client, editor_token, "technology", "wordpress:6.0")
        r = _create_relationship(client, editor_token, tech_id, domain_id, "runs_on")
        assert r.status_code == 400

    def test_nonexistent_source_asset_returns_404(self, client, editor_token):
        """Creating a relationship with a non-existent source returns 404."""
        target_id = _create_asset(client, editor_token, "domain", "exists.com")
        r = _create_relationship(
            client, editor_token,
            "00000000-0000-0000-0000-000000000000",  # ghost ID
            target_id,
            "part_of",
        )
        assert r.status_code == 404

    def test_nonexistent_target_asset_returns_404(self, client, editor_token):
        """Creating a relationship with a non-existent target returns 404."""
        source_id = _create_asset(client, editor_token, "subdomain", "src.exists.com")
        r = _create_relationship(
            client, editor_token,
            source_id,
            "00000000-0000-0000-0000-000000000000",  # ghost ID
            "part_of",
        )
        assert r.status_code == 404


# =============================================================================
# Idempotency — Duplicate Edge Handling
# =============================================================================

class TestRelationshipIdempotency:

    def test_duplicate_edge_returns_existing_record(self, client, editor_token):
        """POSTing an identical relationship twice returns the existing record (no duplicate)."""
        domain_id = _create_asset(client, editor_token, "domain", "idempotent-domain.com")
        sub_id = _create_asset(client, editor_token, "subdomain", "api.idempotent-domain.com")

        r1 = _create_relationship(client, editor_token, sub_id, domain_id, "part_of")
        r2 = _create_relationship(client, editor_token, sub_id, domain_id, "part_of")

        assert r1.status_code == 201
        assert r2.status_code == 201
        # Both should return the same relationship ID
        assert r1.json()["id"] == r2.json()["id"]

    def test_different_type_same_pair_creates_new_edge(self, client, editor_token):
        """Same source/target with a different relationship type creates a distinct edge."""
        domain_id = _create_asset(client, editor_token, "domain", "multi-rel.com")
        sub_id = _create_asset(client, editor_token, "subdomain", "sub.multi-rel.com")

        r1 = _create_relationship(client, editor_token, sub_id, domain_id, "part_of")
        r2 = _create_relationship(client, editor_token, sub_id, domain_id, "alias_of")

        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]


# =============================================================================
# Graph Traversal — GET /relationships/graph/{asset_id}
# =============================================================================

class TestGraphTraversal:

    def test_graph_returns_center_node_and_connected_nodes(self, client, editor_token):
        """Graph endpoint returns the center asset + all directly connected assets as nodes."""
        domain_id = _create_asset(client, editor_token, "domain", "graph-center.com")
        sub1_id = _create_asset(client, editor_token, "subdomain", "sub1.graph-center.com")
        sub2_id = _create_asset(client, editor_token, "subdomain", "sub2.graph-center.com")

        _create_relationship(client, editor_token, sub1_id, domain_id, "part_of")
        _create_relationship(client, editor_token, sub2_id, domain_id, "part_of")

        r = client.get(f"/relationships/graph/{domain_id}")
        assert r.status_code == 200
        data = r.json()

        node_ids = {n["id"] for n in data["nodes"]}
        assert domain_id in node_ids
        assert sub1_id in node_ids
        assert sub2_id in node_ids

    def test_graph_returns_correct_edges(self, client, editor_token):
        """Graph endpoint edges array correctly reflects all relationships touching the center."""
        domain_id = _create_asset(client, editor_token, "domain", "edge-center.com")
        sub_id = _create_asset(client, editor_token, "subdomain", "sub.edge-center.com")

        rel_r = _create_relationship(client, editor_token, sub_id, domain_id, "part_of")
        rel_id = rel_r.json()["id"]

        r = client.get(f"/relationships/graph/{domain_id}")
        assert r.status_code == 200
        edge_ids = {e["id"] for e in r.json()["edges"]}
        assert rel_id in edge_ids

    def test_graph_nonexistent_asset_returns_404(self, client):
        """Querying graph for a non-existent asset ID returns 404."""
        r = client.get("/relationships/graph/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_graph_isolated_node_has_empty_edges(self, client, editor_token):
        """An asset with no relationships returns itself as the only node with empty edges."""
        domain_id = _create_asset(client, editor_token, "domain", "isolated.com")
        r = client.get(f"/relationships/graph/{domain_id}")
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["id"] == domain_id
        assert data["edges"] == []

    def test_graph_bidirectional_resolution_includes_both_directions(self, client, editor_token):
        """Bidirectional ip_address ↔ subdomain edges both appear in the graph."""
        ip_id = _create_asset(client, editor_token, "ip_address", "10.0.0.10")
        sub_id = _create_asset(client, editor_token, "subdomain", "bi.resolution.com")

        # Both directions are valid per the matrix
        r1 = _create_relationship(client, editor_token, ip_id, sub_id, "resolves_to")
        r2 = _create_relationship(client, editor_token, sub_id, ip_id, "resolves_to")
        assert r1.status_code == 201
        assert r2.status_code == 201

        # Graph from IP perspective
        r = client.get(f"/relationships/graph/{ip_id}")
        data = r.json()
        node_ids = {n["id"] for n in data["nodes"]}
        assert sub_id in node_ids
        assert len(data["edges"]) == 2

    def test_unauthenticated_relationship_creation_returns_401(self, client, editor_token):
        """Creating a relationship without a token returns 401."""
        domain_id = _create_asset(client, editor_token, "domain", "auth-check.com")
        sub_id = _create_asset(client, editor_token, "subdomain", "sub.auth-check.com")
        r = client.post(
            "/relationships/",
            json={"source_id": sub_id, "target_id": domain_id, "type": "part_of"},
        )
        assert r.status_code == 401
