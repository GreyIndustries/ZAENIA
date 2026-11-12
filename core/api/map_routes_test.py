from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI, HTTPException, Request

from core.api.map_routes import create_map_router


class MapRouteBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        def authenticated(request: Request):
            if request.headers.get("x-test-owner") != "fixture":
                raise HTTPException(401, "Authentication required")
        application = FastAPI()
        application.include_router(create_map_router(authenticated))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_marine_never_calls_feed_before_authentication(self):
        with patch("core.maps.marine.snapshot") as snapshot:
            response = await self.client.get("/api/map/marine?south=47&west=-123&north=48&east=-122")
        self.assertEqual(response.status_code, 401)
        snapshot.assert_not_called()

    async def test_marine_passes_valid_bounds_without_exposing_credentials(self):
        expected = {"ships": [], "configured": False, "source": "none"}
        with patch("core.maps.marine.snapshot", return_value=expected) as snapshot:
            response = await self.client.get("/api/map/marine?south=47&west=-123&north=48&east=-122", headers={"x-test-owner": "fixture"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        snapshot.assert_called_once_with(47.0, -123.0, 48.0, -122.0)

    async def test_malformed_bounds_are_rejected_without_feed_call(self):
        with patch("core.maps.marine.snapshot") as snapshot:
            response = await self.client.get("/api/map/marine?south=91&west=-123&north=48&east=-122", headers={"x-test-owner": "fixture"})
        self.assertEqual(response.status_code, 422)
        snapshot.assert_not_called()

    async def test_route_still_requires_authentication(self):
        with patch("core.maps.live.route") as route:
            response = await self.client.post("/api/map/route", json={"stops": [{"lat": 47, "lon": -123}, {"lat": 48, "lon": -122}]})
        self.assertEqual(response.status_code, 401)
        route.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class SuggestionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = MapRouteBoundaryTests.asyncSetUp
    asyncTearDown = MapRouteBoundaryTests.asyncTearDown
    async def test_suggestions_require_authentication_before_provider_call(self):
        with patch("core.maps.live.suggest_places") as provider:
            response = await self.client.get("/api/map/search?q=sample&lat=47&lon=-122&autocomplete=true")
        self.assertEqual(response.status_code, 401)
        provider.assert_not_called()

    async def test_autocomplete_uses_separate_provider_and_validates_location(self):
        with patch("core.maps.live.suggest_places", return_value={"places": [], "source": "photon"}) as provider, patch("core.maps.live.search_places") as explicit:
            response = await self.client.get("/api/map/search?q=sample&lat=47&lon=-122&autocomplete=true", headers={"x-test-owner": "fixture"})
            self.assertEqual(response.status_code, 200)
            provider.assert_called_once_with("sample", 47.0, -122.0)
            explicit.assert_not_called()
            provider.reset_mock()
            invalid = await self.client.get("/api/map/search?q=sample&lat=91&lon=-122&autocomplete=true", headers={"x-test-owner": "fixture"})
            self.assertEqual(invalid.status_code, 422)
            provider.assert_not_called()


    async def test_home_advertises_suggestion_support_for_mixed_version_clients(self):
        with patch("core.maps.service.home", return_value={"place": "Sample"}):
            response = await self.client.get("/api/map/home", headers={"x-test-owner": "fixture"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["features"], {"autocomplete": True, "alternatives": True})
