"""Content-based music recommender for MindEase.

Data: Kaggle "Spotify Tracks Dataset" (maharshipandya). Save the CSV as
data/spotify_tracks.csv (or set MUSIC_CSV). Needs: pandas, numpy.

Idea: each mood has a TARGET audio profile. Sad/angry/stressed users get
gently uplifting or calming targets, not songs that match their mood.
Tracks are ranked by distance to the target; we sample from the closest
pool so repeat visits are not identical.
"""
import os
import random
from functools import lru_cache

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, session

CSV_PATH = os.environ.get("MUSIC_CSV", os.path.join("data", "spotify_tracks.csv"))
FEATURES = ["valence", "energy", "danceability", "acousticness", "instrumentalness", "tempo_n"]

# target profile per selected mood (values 0..1; tempo_n = tempo / 200)
TARGETS = {
    "happy":    dict(valence=.85, energy=.75, danceability=.75, acousticness=.15, instrumentalness=.0, tempo_n=.62),
    "sad":      dict(valence=.55, energy=.45, danceability=.55, acousticness=.50, instrumentalness=.05, tempo_n=.52),
    "stressed": dict(valence=.50, energy=.20, danceability=.40, acousticness=.80, instrumentalness=.60, tempo_n=.45),
    "angry":    dict(valence=.45, energy=.30, danceability=.40, acousticness=.70, instrumentalness=.30, tempo_n=.48),
}
WEIGHTS = np.array([2.0, 2.0, 1.0, 1.0, .7, .5])  # valence and energy matter most


def label_mood(valence, energy):
    """Valence/energy quadrant label, useful for charts or tagging the dataset."""
    if valence >= .5:
        return "happy" if energy >= .5 else "calm"
    return "angry" if energy >= .5 else "sad"


@lru_cache(maxsize=1)
def _load():
    if not os.path.exists(CSV_PATH):
        return None
    cols = ["track_id", "track_name", "artists", "popularity", "explicit", "valence", "energy",
            "danceability", "acousticness", "instrumentalness", "tempo"]
    df = pd.read_csv(CSV_PATH, usecols=lambda c: c in cols + ["track_genre"])
    df = df.dropna(subset=["track_id", "track_name", "valence", "energy", "tempo"])
    df = df.drop_duplicates(subset=["track_id"]).drop_duplicates(subset=["track_name", "artists"])
    df = df[(df["popularity"] >= 30) & (df["tempo"] > 0)].copy()
    df["tempo_n"] = (df["tempo"] / 200).clip(0, 1)
    df = df.reset_index(drop=True)
    return df, df[FEATURES].to_numpy(dtype=float)


def recommend(mood, n=10, pool=60, clean_only=True):
    loaded = _load()
    mood = (mood or "").lower()
    if loaded is None or mood not in TARGETS:
        return []
    df, mat = loaded
    target = np.array([TARGETS[mood][f] for f in FEATURES])
    dist = np.sqrt((((mat - target) ** 2) * WEIGHTS).sum(axis=1))
    if clean_only and "explicit" in df.columns:
        dist = np.where(df["explicit"].astype(bool).to_numpy(), np.inf, dist)
    idx = np.argsort(dist)[:pool]
    idx = [i for i in idx if np.isfinite(dist[i])]
    picks = random.sample(idx, min(n, len(idx)))
    return [{"id": df.at[i, "track_id"],
             "title": str(df.at[i, "track_name"]),
             "artist": str(df.at[i, "artists"]).replace(";", ", "),
             "url": "https://open.spotify.com/track/" + str(df.at[i, "track_id"]),
             "embed": "https://open.spotify.com/embed/track/" + str(df.at[i, "track_id"])}
            for i in picks]


def create_music_blueprint():
    bp = Blueprint("music_reco", __name__)

    @bp.route("/api/music/<mood>")
    def api_music(mood):
        if "user" not in session:
            return jsonify(error="Please log in again."), 401
        if mood.lower() not in TARGETS:
            return jsonify(error="Unknown mood."), 404
        tracks = recommend(mood)
        if not tracks:
            return jsonify(tracks=[], note="Recommendations are unavailable right now."), 200
        return jsonify(tracks=tracks)

    return bp
