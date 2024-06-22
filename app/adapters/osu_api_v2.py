import logging
from datetime import datetime
from datetime import timezone
from enum import IntEnum
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel
from pydantic import Field

from app import oauth
from app import settings
from app.common_models import GameMode
from app.common_models import RankedStatus

OSU_API_V2_TOKEN_ENDPOINT = "https://osu.ppy.sh/oauth/token"


async def log_osu_api_response(response: httpx.Response) -> None:
    if response.request.url == OSU_API_V2_TOKEN_ENDPOINT or response.status_code == 401:
        return None

    # TODO: Migrate to or add statsd metric to count overall number of
    #       authorized requests to the osu! api, so we can understand
    #       our overall request count and frequency.
    logging.info(
        "Made authorized request to osu! api",
        extra={
            "request_url": response.request.url,
            "ratelimit": {
                "remaining": response.headers.get("X-Ratelimit-Remaining"),
                "limit": response.headers.get("X-Ratelimit-Limit"),
                "reset_utc": (
                    # they don't send a header, but reset on the minute
                    datetime.now(tz=timezone.utc)
                    .replace(second=0, microsecond=0)
                    .isoformat()
                ),
            },
        },
    )
    return None


osu_api_v2_http_client = httpx.AsyncClient(
    base_url="https://osu.ppy.sh/api/v2/",
    auth=oauth.AsyncOAuth(
        client_id=settings.OSU_API_V2_CLIENT_ID,
        client_secret=settings.OSU_API_V2_CLIENT_SECRET,
        token_endpoint=OSU_API_V2_TOKEN_ENDPOINT,
    ),
    event_hooks={"response": [log_osu_api_response]},
    timeout=5.0,
)


class Ruleset(StrEnum):
    OSU = "osu"
    TAIKO = "taiko"
    FRUITS = "fruits"
    MANIA = "mania"


class Failtimes(BaseModel):
    exit: list[int]  # TODO: nullable? osu api says yes
    fail: list[int]  # TODO: nullable? osu api says yes


class Beatmap(BaseModel):
    beatmapset_id: int
    difficulty_rating: float
    id: int
    mode: Ruleset
    status: str  # ranked status (TODO enum?)
    total_length: int
    user_id: int
    version: str

    # TODO: enable this, if desired
    # - Beatmapset for Beatmap objects
    # - BeatmapsetExtended for BeatmapExtended objects
    # - None if there is no associated set (e.g. deleted)
    # beatmapset: Beatmapset | BeatmapsetExtended | None

    checksum: str | None
    failtimes: Failtimes | None = None
    max_combo: int | None = None
    bpm: float


class BeatmapExtended(Beatmap):
    accuracy: float
    ar: float
    beatmapset_id: int
    convert: bool
    count_circles: int
    count_sliders: int
    count_spinners: int
    cs: float
    deleted_at: datetime | None
    drain: float
    hit_length: int
    is_scoreable: bool
    last_updated: datetime
    mode_int: int
    passcount: int
    playcount: int
    ranked: int  # TODO: enum
    url: str


async def get_beatmap(beatmap_id: int) -> BeatmapExtended | None:
    osu_api_response_data: dict[str, Any] | None = None
    try:
        response = await osu_api_v2_http_client.get(f"beatmaps/{beatmap_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        osu_api_response_data = response.json()
        assert osu_api_response_data is not None
        return BeatmapExtended(**osu_api_response_data)
    except Exception:
        logging.exception(
            "Failed to fetch beatmap from osu! API",
            extra={"osu_api_response_data": osu_api_response_data},
        )
        raise


class Covers(BaseModel):
    cover: str
    cover2x: str = Field(alias="cover@2x")
    card: str
    card2x: str = Field(alias="card@2x")
    list: str
    list2x: str = Field(alias="list@2x")
    slimcover: str
    slimcover2x: str = Field(alias="slimcover@2x")


class RequiredMeta(BaseModel):
    main_ruleset: int
    non_main_ruleset: int


class NominationsSummary(BaseModel):
    current: int
    eligible_main_rulesets: list[Ruleset] | None = None
    required_meta: RequiredMeta


class Availability(BaseModel):
    download_disabled: bool
    more_information: str | None


class Genre(BaseModel):
    id: int
    name: str


class Description(BaseModel):
    description: str  # (html string)


class Language(BaseModel):
    id: int
    name: str


class Beatmapset(BaseModel):
    artist: str
    artist_unicode: str | None
    covers: Covers
    creator: str
    favourite_count: int
    hype: Any | None  # TODO
    id: int
    nsfw: bool
    offset: int
    play_count: int
    preview_url: str
    source: str
    spotlight: bool
    status: str  # TODO enum
    title: str
    title_unicode: str | None
    user_id: int
    video: bool


class BeatmapsetExtended(Beatmapset):
    bpm: float | None
    can_be_hyped: bool
    deleted_at: datetime | None
    discussion_enabled: bool
    discussion_locked: bool
    is_scoreable: bool
    last_updated: datetime
    legacy_thread_url: str
    nominations_summary: NominationsSummary
    ranked: int  # TODO: enum
    ranked_date: datetime | None
    storyboard: bool
    submitted_date: datetime
    tags: str

    availability: Availability

    beatmaps: list[BeatmapExtended] | None
    converts: list[BeatmapExtended] | None = None
    current_nominations: list[Any] | None = None
    current_user_attributes: Any | None = None  # TODO
    description: Description | None = None
    discussions: Any = None  # TODO
    events: Any | None = None  # TODO
    genre: Genre | None = None
    has_favourited: Any = None  # TODO
    language: Language | None = None
    pack_tags: list[str] | None
    ratings: Any | None = None  # TODO
    recent_favourites: Any | None = None  # TODO
    related_users: Any | None = None  # TODO
    user: Any | None = None  # TODO
    track_id: int | None


async def get_beatmapset(beatmapset_id: int) -> BeatmapsetExtended | None:
    osu_api_response_data: dict[str, Any] | None = None
    try:
        response = await osu_api_v2_http_client.get(f"beatmapsets/{beatmapset_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        osu_api_response_data = response.json()
        assert osu_api_response_data is not None
        return BeatmapsetExtended(**osu_api_response_data)
    except Exception:
        logging.exception(
            "Failed to fetch beatmapset from osu! API",
            extra={"osu_api_response_data": osu_api_response_data},
        )
        raise


class Cursor(BaseModel):
    approved_date: int | None = None
    score: float | None = Field(alias="_score")
    id: int


class Search(BaseModel):
    sort: str  # TODO: enum


class BeatmapsetSearchResponse(BaseModel):
    beatmapsets: list[BeatmapsetExtended]
    cursor: Cursor
    cursor_string: str
    error: Any | None
    recommended_difficulty: float | None
    search: Search
    total: int


class SearchLegacyRankedStatus(IntEnum):
    RANKED = 0
    FAVOURITES = 2
    QUALIFIED = 3
    PENDING = 4
    GRAVEYARD = 5
    MINE = 6
    ANY = 7
    LOVED = 8

    @classmethod
    def from_osu_api_status(
        cls,
        osu_api_status: RankedStatus,
    ) -> "SearchLegacyRankedStatus | None":
        return {
            RankedStatus.NOT_SUBMITTED: None,
            RankedStatus.PENDING: SearchLegacyRankedStatus.PENDING,
            RankedStatus.UPDATE_AVAILABLE: None,
            RankedStatus.RANKED: SearchLegacyRankedStatus.RANKED,
            RankedStatus.APPROVED: SearchLegacyRankedStatus.RANKED,
            RankedStatus.QUALIFIED: SearchLegacyRankedStatus.QUALIFIED,
            RankedStatus.LOVED: SearchLegacyRankedStatus.LOVED,
        }.get(osu_api_status)


async def search_beatmapsets(
    query: str,
    *,
    ranked_status: SearchLegacyRankedStatus,
    mode: GameMode,
    page: int,
    page_size: int,
    cursor_string: str | None = None,
) -> BeatmapsetSearchResponse:
    # TODO: support more parameters. Here is a sample query:
    # https://osu.ppy.sh/beatmapsets/search?e=&c=&g=&l=&m=&nsfw=&played=&q=&r=&sort=&s=&cursor_string=eyJhcHByb3ZlZF9kYXRlIjoxNzE4ODQ3Nzk0MDAwLCJpZCI6MjEzNDYyNX0

    osu_api_response_data: dict[str, Any] | None = None
    try:
        response = await osu_api_v2_http_client.get(
            "beatmapsets/search",
            params={
                "q": query,
                "m": mode,
                "r": ranked_status,
                "page": page,
                "limit": page_size,
                "cursor_string": cursor_string,
            },
        )
        response.raise_for_status()
        osu_api_response_data = response.json()
        assert osu_api_response_data is not None
        return BeatmapsetSearchResponse(**osu_api_response_data)
    except Exception:
        logging.exception(
            "Failed to fetch beatmapsets from osu! API",
            extra={"osu_api_response_data": osu_api_response_data},
        )
        raise
