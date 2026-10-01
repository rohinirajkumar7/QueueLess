import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
@pytest.mark.asyncio
async def test_health():
 async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as c:
  r=await c.get("/health"); assert r.status_code==200 and r.json()["status"]=="ok"
