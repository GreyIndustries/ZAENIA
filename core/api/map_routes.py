"""LIFE > Map & traffic routes: saved map tiles, landmarks and WSDOT traffic (core/maps/service.py).

Same token check and client gate as the other UI routes; every path here is a read (status.read in
ui_routes.OPERATION_PATTERNS). Tiles travel as base64 JSON so the desktop bridge, which carries JSON, can pass them.
"""
from __future__ import annotations

import base64
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field


class Stop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stops: list[Stop] = Field(min_length=2, max_length=12)
    bestOrder: bool = False
    alternatives: bool = False


def create_map_router(require_api_authentication: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/api/map", dependencies=[Depends(require_api_authentication)], tags=["map"])

    @router.get("/home")
    def map_home() -> dict[str, Any]:
        from core.maps import service
        return {**service.home(), "features": {"autocomplete": True, "alternatives": True}}

    @router.get("/tile/{z}/{x}/{y}")
    def map_tile(z: int = Path(ge=0, le=18), x: int = Path(ge=0, le=262_143), y: int = Path(ge=0, le=262_143),
                 style: str = Query(default="clear", pattern=r"^(clear|satellite|labels|dark|standard)$")) -> dict[str, Any]:
        from core.maps import service
        try:
            body, source = service.tile(z, x, y, style)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except service.MapUnavailable as error:
            raise HTTPException(404, str(error)) from error
        return {"png": base64.b64encode(body).decode("ascii"), "mime": service.tile_mime(body), "source": source}

    @router.get("/landmarks")
    def map_landmarks(south: float = Query(ge=-90, le=90), west: float = Query(ge=-180, le=180),
                      north: float = Query(ge=-90, le=90), east: float = Query(ge=-180, le=180)) -> dict[str, Any]:
        from core.maps import service
        try:
            return service.landmarks(south, west, north, east)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/traffic/segments")
    def map_traffic_segments() -> dict[str, Any]:
        from core.maps import service
        return service.traffic_segments()

    @router.get("/traffic")
    def map_traffic(refresh: bool = Query(default=False)) -> dict[str, Any]:
        from core.maps import service
        return service.traffic(force=refresh)

    # ---- directions, place search, weather, air traffic (core/maps/live.py)
    @router.post("/route")
    def map_route(body: RouteBody) -> dict[str, Any]:
        from core.maps import live
        try:
            return live.route([stop.model_dump() for stop in body.stops], best_order=body.bestOrder, **({"alternatives": True} if body.alternatives else {}))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except ConnectionError as error:
            raise HTTPException(503, str(error)) from error

    @router.get("/search")
    def map_search(q: str = Query(min_length=1, max_length=120), lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), autocomplete: bool = False) -> dict[str, Any]:
        from core.maps import live
        return live.suggest_places(q, lat, lon) if autocomplete else live.search_places(q, lat, lon)

    @router.get("/weather/alerts")
    def map_weather_alerts(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)) -> dict[str, Any]:
        from core.maps import live
        return live.weather_alerts(lat, lon)

    @router.get("/radar")
    def map_radar() -> dict[str, Any]:
        from core.maps import live
        return live.radar_frames()

    @router.get("/radar/tile/{z}/{x}/{y}")
    def map_radar_tile(z: int = Path(ge=0, le=7), x: int = Path(ge=0, le=127), y: int = Path(ge=0, le=127),
                       path: str = Query(min_length=10, max_length=80)) -> dict[str, Any]:
        from core.maps import live
        try:
            return {"png": base64.b64encode(live.radar_tile(path, z, x, y)).decode("ascii")}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except Exception as error:
            raise HTTPException(404, "Radar isn't available for this spot right now.") from error

    @router.get("/aircraft")
    def map_aircraft(south: float = Query(ge=-90, le=90), west: float = Query(ge=-180, le=180),
                     north: float = Query(ge=-90, le=90), east: float = Query(ge=-180, le=180)) -> dict[str, Any]:
        from core.maps import live
        try:
            return live.aircraft(south, west, north, east)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/marine")
    def map_marine(south: float = Query(ge=-90, le=90), west: float = Query(ge=-180, le=180),
                   north: float = Query(ge=-90, le=90), east: float = Query(ge=-180, le=180)) -> dict[str, Any]:
        from core.maps import marine
        try:
            return marine.snapshot(south, west, north, east)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    return router
