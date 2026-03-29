"""Spotify music tool for Eddie."""

import json
import logging

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from thefuzz import process

from eddie.config import get_config

logger = logging.getLogger(__name__)


class MusicManager:
    """Manages Spotify playback with fuzzy search."""

    def __init__(self) -> None:
        config = get_config()
        self.spotify: spotipy.Spotify | None = None
        self.data: dict = {}

        try:
            auth = SpotifyOAuth(
                open_browser=False,
                redirect_uri=config.spotify_redirect_uri,
                client_id=config.spotify_client_id,
                client_secret=config.spotify_client_secret,
                scope="user-read-playback-state,user-modify-playback-state,streaming",
            )
            self.spotify = spotipy.Spotify(client_credentials_manager=auth)
        except Exception:
            logger.exception("Failed to initialize Spotify client")

        try:
            with open(config.spotify_data_path, encoding="utf-8") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            logger.warning("Spotify data file not found at %s", config.spotify_data_path)
        except Exception:
            logger.exception("Failed to load Spotify data")

    def fuzzy_search(self, name: str, category: str, artist_name: str | None = None) -> tuple[str | None, str | None]:
        """Fuzzy search for an artist, album, or track in local Spotify data."""
        choices: dict[str, str] = {}

        if category == "artists":
            choices = {k: v["uri"] for k, v in self.data.get("artists", {}).items()}
        elif category in ("albums", "tracks") and artist_name:
            artist_data = self.data.get("artists", {}).get(artist_name)
            if artist_data:
                for album_name, album_data in artist_data.get("albums", {}).items():
                    if category == "albums":
                        choices[album_name] = album_data["uri"]
                    else:
                        for track_name, track_uri in album_data.get("tracks", {}).items():
                            choices[track_name] = track_uri
        else:
            for artist in self.data.get("artists", {}).values():
                for album_name, album_data in artist.get("albums", {}).items():
                    if category == "albums":
                        choices[album_name] = album_data["uri"]
                    else:
                        for track_name, track_uri in album_data.get("tracks", {}).items():
                            choices[track_name] = track_uri

        if not choices:
            return None, None

        # Decreasing threshold fuzzy search
        threshold = 60
        while threshold > 0:
            result = process.extractOne(name, list(choices.keys()), score_cutoff=threshold)
            if result is not None:
                best_match, score = result[0], result[1]
                if score > threshold:
                    uri = choices[best_match]
                    if category == "tracks":
                        uri = f"spotify:track:{uri}"
                    return best_match, uri
            threshold -= 10

        return None, None

    def play(self, query: str, artist: str | None = None) -> str:
        """Play music by searching for a song, artist, or album."""
        if not self.spotify:
            return "Spotify is not configured."

        # Try to find artist first if specified
        matched_artist = None
        if artist:
            matched_artist, _ = self.fuzzy_search(artist, "artists")

        # Try as a track first
        if matched_artist:
            track_name, track_uri = self.fuzzy_search(query, "tracks", matched_artist)
            if track_uri:
                return self._start_playback(track_name, matched_artist, uris=[track_uri])

            # Try as album
            album_name, album_uri = self.fuzzy_search(query, "albums", matched_artist)
            if album_uri:
                return self._start_playback(album_name, matched_artist, context_uri=album_uri)

        # Try as artist
        artist_name, artist_uri = self.fuzzy_search(query, "artists")
        if artist_uri:
            return self._start_playback(None, artist_name, context_uri=artist_uri)

        # Try as track across all artists
        track_name, track_uri = self.fuzzy_search(query, "tracks")
        if track_uri:
            return self._start_playback(track_name, None, uris=[track_uri])

        return f"Couldn't find anything matching '{query}' in the music library."

    def _start_playback(
        self,
        track: str | None,
        artist: str | None,
        uris: list[str] | None = None,
        context_uri: str | None = None,
    ) -> str:
        try:
            if uris:
                self.spotify.start_playback(uris=uris)
            elif context_uri:
                self.spotify.start_playback(context_uri=context_uri)
            else:
                return "No URI to play."

            desc = ""
            if track and artist:
                desc = f"{track} by {artist}"
            elif artist:
                desc = artist
            elif track:
                desc = track

            logger.info("Now playing: %s", desc)
            return f"Now playing {desc}."
        except Exception:
            logger.exception("Failed to start playback")
            return "Failed to start playback. Make sure Spotify is active on a device."

    def pause(self) -> str:
        """Pause playback."""
        if not self.spotify:
            return "Spotify is not configured."
        try:
            self.spotify.pause_playback()
            return "Music paused."
        except Exception:
            logger.exception("Failed to pause")
            return "Failed to pause playback."

    def skip(self) -> str:
        """Skip to next track."""
        if not self.spotify:
            return "Spotify is not configured."
        try:
            self.spotify.next_track()
            return "Skipped to next track."
        except Exception:
            logger.exception("Failed to skip")
            return "Failed to skip track."
