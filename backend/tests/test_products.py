import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from digitalcard.core.config import get_settings
from digitalcard.main import app
from test_tenancy import bootstrap_two_companies, headers, sign_in

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    settings = get_settings()
    previous_upload_dir = settings.upload_dir
    upload_dir = Path("data/test-uploads") / str(uuid4())
    settings.upload_dir = str(upload_dir)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value
    settings.upload_dir = previous_upload_dir
    shutil.rmtree(upload_dir, ignore_errors=True)


async def upload(
    client: AsyncClient,
    session: dict[str, object],
    name: str,
    content_type: str,
    content: bytes,
    access: str = "private",
):  # type: ignore[no-untyped-def]
    return await client.post(
        f"/api/v1/tenant/materials?name={name}&access={access}",
        headers={**headers(session), "Content-Type": content_type},
        content=content,
    )


async def create_product(
    client: AsyncClient,
    session: dict[str, object],
    name: str,
    cover_id: str,
    sort_order: int = 0,
):  # type: ignore[no-untyped-def]
    response = await client.post(
        "/api/v1/tenant/products",
        headers=headers(session),
        json={
            "name": name,
            "summary": f"{name}介绍",
            "cover_material_id": cover_id,
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_upload_validation_access_and_reference_protection(client: AsyncClient) -> None:
    _, _, _ = await bootstrap_two_companies(client)
    admin = await sign_in(client, "admin-a@example.com")
    invalid = await upload(client, admin, "fake.png", "image/png", b"not-a-png")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "material_content_mismatch"
    materials = await client.get("/api/v1/tenant/materials", headers=headers(admin))
    assert materials.json() == []

    private = await upload(
        client,
        admin,
        "cover.png",
        "image/png",
        b"\x89PNG\r\n\x1a\n" + b"test-image",
    )
    assert private.status_code == 201, private.text
    material_id = private.json()["id"]
    assert (await client.get(f"/api/v1/public/materials/{material_id}")).status_code == 404

    product = await create_product(client, admin, "产品 A", material_id)
    publish = await client.post(
        f"/api/v1/tenant/products/{product['id']}/status",
        headers=headers(admin),
        json={"status": "published"},
    )
    assert publish.status_code == 409
    assert publish.json()["error"]["code"] == "product_material_not_public"

    access = await client.patch(
        f"/api/v1/tenant/materials/{material_id}/access",
        headers=headers(admin),
        json={"access": "public"},
    )
    assert access.status_code == 200
    publish = await client.post(
        f"/api/v1/tenant/products/{product['id']}/status",
        headers=headers(admin),
        json={"status": "published"},
    )
    assert publish.status_code == 200, publish.text
    assert (await client.get(f"/api/v1/public/products/{product['id']}")).status_code == 200
    assert (await client.get(f"/api/v1/public/materials/{material_id}")).status_code == 200

    replacement = await upload(
        client,
        admin,
        "private-replacement.png",
        "image/png",
        b"\x89PNG\r\n\x1a\n" + b"replacement",
    )
    replace_cover = await client.patch(
        f"/api/v1/tenant/products/{product['id']}",
        headers=headers(admin),
        json={"cover_material_id": replacement.json()["id"]},
    )
    assert replace_cover.status_code == 409
    assert replace_cover.json()["error"]["code"] == "product_material_not_public"

    make_private = await client.patch(
        f"/api/v1/tenant/materials/{material_id}/access",
        headers=headers(admin),
        json={"access": "private"},
    )
    assert make_private.status_code == 409
    assert make_private.json()["error"]["code"] == "material_in_published_product"
    deleted = await client.delete(f"/api/v1/tenant/materials/{material_id}", headers=headers(admin))
    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "material_in_use"
    assert deleted.json()["error"]["details"]["references"][0]["id"] == product["id"]

    offline = await client.post(
        f"/api/v1/tenant/products/{product['id']}/status",
        headers=headers(admin),
        json={"status": "offline"},
    )
    assert offline.status_code == 200
    assert (await client.get(f"/api/v1/public/products/{product['id']}")).status_code == 404


async def test_recommended_product_order_only_changes_after_card_publish(
    client: AsyncClient,
) -> None:
    _, _, _ = await bootstrap_two_companies(client)
    admin = await sign_in(client, "admin-a@example.com")
    cover = await upload(
        client,
        admin,
        "public-cover.png",
        "image/png",
        b"\x89PNG\r\n\x1a\n" + b"public-image",
        "public",
    )
    cover_id = cover.json()["id"]
    first = await create_product(client, admin, "第一产品", cover_id, 20)
    second = await create_product(client, admin, "第二产品", cover_id, 10)
    for product in (first, second):
        response = await client.post(
            f"/api/v1/tenant/products/{product['id']}/status",
            headers=headers(admin),
            json={"status": "published"},
        )
        assert response.status_code == 200

    ordered = await client.get("/api/v1/tenant/products", headers=headers(admin))
    assert [item["name"] for item in ordered.json()["items"]] == ["第二产品", "第一产品"]
    recommendation = await client.put(
        "/api/v1/tenant/cards/me/recommendations",
        headers=headers(admin),
        json={"product_ids": [first["id"], second["id"]]},
    )
    assert recommendation.status_code == 200, recommendation.text
    card = await client.post("/api/v1/tenant/cards/me/publish", headers=headers(admin))
    assert card.status_code == 200, card.text
    card_id = card.json()["id"]
    public_products = await client.get(f"/api/v1/public/cards/{card_id}/products")
    assert [item["id"] for item in public_products.json()] == [first["id"], second["id"]]

    changed = await client.put(
        "/api/v1/tenant/cards/me/recommendations",
        headers=headers(admin),
        json={"product_ids": [second["id"], first["id"]]},
    )
    assert changed.status_code == 200
    unchanged_public = await client.get(f"/api/v1/public/cards/{card_id}/products")
    assert [item["id"] for item in unchanged_public.json()] == [first["id"], second["id"]]
    await client.post("/api/v1/tenant/cards/me/publish", headers=headers(admin))
    updated_public = await client.get(f"/api/v1/public/cards/{card_id}/products")
    assert [item["id"] for item in updated_public.json()] == [second["id"], first["id"]]
