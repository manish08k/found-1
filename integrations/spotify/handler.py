"""
Spotify Web API integration.

Credential fields:
  - access_token: Spotify OAuth2 access token (Authorization: Bearer)

Auth: Bearer token
Base URL: https://api.spotify.com/v1
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

SPOTIFY_BASE_URL = "https://api.spotify.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Spotify credential is missing 'access_token'")
    return httpx.AsyncClient(
        base_url=SPOTIFY_BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Spotify API error {r.status_code}: {detail}")
    if r.status_code == 204:
        return {"ok": True}
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("spotify.get_current_user")
async def spotify_get_current_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me — get current user's profile."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
    return _check(r)


@register_node("spotify.search")
async def spotify_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /search — search for tracks, artists, albums, or playlists."""
    q = config.get("q") or input_data.get("q")
    if not q:
        raise ValueError("spotify.search requires 'q'")
    params: dict = {"q": q}
    type_ = config.get("type") or input_data.get("type", "track,artist,album")
    params["type"] = type_
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = min(int(limit), 50)
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        params["offset"] = int(offset)
    market = config.get("market") or input_data.get("market")
    if market:
        params["market"] = market
    async with await _client(credential_id, db) as client:
        r = await client.get("/search", params=params)
    return _check(r)


@register_node("spotify.get_track")
async def spotify_get_track(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /tracks/{id} — get a track by ID."""
    track_id = config.get("track_id") or input_data.get("track_id")
    if not track_id:
        raise ValueError("spotify.get_track requires 'track_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/tracks/{track_id}")
    return _check(r)


@register_node("spotify.get_artist")
async def spotify_get_artist(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /artists/{id} — get an artist by ID."""
    artist_id = config.get("artist_id") or input_data.get("artist_id")
    if not artist_id:
        raise ValueError("spotify.get_artist requires 'artist_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/artists/{artist_id}")
    return _check(r)


@register_node("spotify.get_album")
async def spotify_get_album(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /albums/{id} — get an album by ID."""
    album_id = config.get("album_id") or input_data.get("album_id")
    if not album_id:
        raise ValueError("spotify.get_album requires 'album_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/albums/{album_id}")
    return _check(r)


@register_node("spotify.list_playlists")
async def spotify_list_playlists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me/playlists — list current user's playlists."""
    params: dict = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = min(int(limit), 50)
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        params["offset"] = int(offset)
    async with await _client(credential_id, db) as client:
        r = await client.get("/me/playlists", params=params)
    return _check(r)


@register_node("spotify.create_playlist")
async def spotify_create_playlist(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /users/{user_id}/playlists — create a new playlist."""
    user_id = config.get("user_id") or input_data.get("user_id")
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("spotify.create_playlist requires 'name'")
    body: dict = {"name": name}
    description = config.get("description") or input_data.get("description")
    if description:
        body["description"] = description
    public = config.get("public")
    if public is None:
        public = input_data.get("public")
    if public is not None:
        body["public"] = bool(public)
    async with await _client(credential_id, db) as client:
        if not user_id:
            me = await client.get("/me")
            user_id = _check(me)["id"]
        r = await client.post(f"/users/{user_id}/playlists", json=body)
    return _check(r)


@register_node("spotify.add_tracks_to_playlist")
async def spotify_add_tracks_to_playlist(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /playlists/{id}/tracks — add tracks to a playlist."""
    playlist_id = config.get("playlist_id") or input_data.get("playlist_id")
    uris = config.get("uris") or input_data.get("uris")
    if not playlist_id:
        raise ValueError("spotify.add_tracks_to_playlist requires 'playlist_id'")
    if not uris:
        raise ValueError("spotify.add_tracks_to_playlist requires 'uris'")
    body: dict = {"uris": uris}
    position = config.get("position") or input_data.get("position")
    if position is not None:
        body["position"] = int(position)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/playlists/{playlist_id}/tracks", json=body)
    return _check(r)


@register_node("spotify.get_recommendations")
async def spotify_get_recommendations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /recommendations — get track recommendations."""
    params: dict = {}
    seed_tracks = config.get("seed_tracks") or input_data.get("seed_tracks")
    if seed_tracks:
        params["seed_tracks"] = ",".join(seed_tracks) if isinstance(seed_tracks, list) else seed_tracks
    seed_artists = config.get("seed_artists") or input_data.get("seed_artists")
    if seed_artists:
        params["seed_artists"] = ",".join(seed_artists) if isinstance(seed_artists, list) else seed_artists
    seed_genres = config.get("seed_genres") or input_data.get("seed_genres")
    if seed_genres:
        params["seed_genres"] = ",".join(seed_genres) if isinstance(seed_genres, list) else seed_genres
    if not any([seed_tracks, seed_artists, seed_genres]):
        raise ValueError("spotify.get_recommendations requires at least one seed (seed_tracks, seed_artists, or seed_genres)")
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = min(int(limit), 100)
    async with await _client(credential_id, db) as client:
        r = await client.get("/recommendations", params=params)
    return _check(r)


@register_node("spotify.get_currently_playing")
async def spotify_get_currently_playing(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me/player/currently-playing — get the currently playing track."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me/player/currently-playing")
    return _check(r)


@register_node("spotify.get_recently_played")
async def spotify_get_recently_played(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me/player/recently-played — get recently played tracks."""
    params: dict = {}
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        params["limit"] = min(int(limit), 50)
    before = config.get("before") or input_data.get("before")
    if before:
        params["before"] = before
    after = config.get("after") or input_data.get("after")
    if after:
        params["after"] = after
    async with await _client(credential_id, db) as client:
        r = await client.get("/me/player/recently-played", params=params)
    return _check(r)


@register_node("spotify.get_available_devices")
async def spotify_get_available_devices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /me/player/devices — get available devices."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me/player/devices")
    return _check(r)


@register_node("spotify.play")
async def spotify_play(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /me/player/play — start or resume playback."""
    body: dict = {}
    context_uri = config.get("context_uri") or input_data.get("context_uri")
    if context_uri:
        body["context_uri"] = context_uri
    uris = config.get("uris") or input_data.get("uris")
    if uris:
        body["uris"] = uris
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        body["offset"] = offset
    params: dict = {}
    device_id = config.get("device_id") or input_data.get("device_id")
    if device_id:
        params["device_id"] = device_id
    async with await _client(credential_id, db) as client:
        r = await client.put("/me/player/play", json=body, params=params)
    return _check(r)


@register_node("spotify.pause")
async def spotify_pause(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /me/player/pause — pause playback."""
    params: dict = {}
    device_id = config.get("device_id") or input_data.get("device_id")
    if device_id:
        params["device_id"] = device_id
    async with await _client(credential_id, db) as client:
        r = await client.put("/me/player/pause", params=params)
    return _check(r)


@register_node("spotify.skip_to_next")
async def spotify_skip_to_next(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /me/player/next — skip to the next track."""
    params: dict = {}
    device_id = config.get("device_id") or input_data.get("device_id")
    if device_id:
        params["device_id"] = device_id
    async with await _client(credential_id, db) as client:
        r = await client.post("/me/player/next", params=params)
    return _check(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test Spotify connection by fetching the current user profile."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/me")
    _check(r)
    return {"ok": True}
