"""Default tour payload for first-time app startup."""

from __future__ import annotations

import copy

_DEFAULT_TOUR = {
    "meta": {
        "name": "Sample Virtual Tour",
        "startScene": "lobby",
    },
    "scenes": {
        "lobby": {
            "id": "lobby",
            "title": "Lobby",
            "panorama": "/images/example-1.jpg",
            "hotSpots": [
                {
                    "pitch": -5,
                    "yaw": 70,
                    "targetScene": "hall",
                    "text": "Go to Hall",
                    "prompt": "Walk into the main hall",
                },
                {
                    "kind": "graph",
                    "pitch": 8,
                    "yaw": 20,
                    "text": "Temperature Trend",
                    "prompt": "Hover to load an animated timeseries graph",
                    "graph": {
                        "csv": "sample_timeseries.csv",
                        "x": "timestamp",
                        "y": "temperature",
                        "yLabel": "Temperature",
                        "yUnit": "C",
                        "animate": True,
                    },
                },
            ],
        },
        "hall": {
            "id": "hall",
            "title": "Main Hall",
            "panorama": "/images/example-2.jpg",
            "hotSpots": [
                {
                    "pitch": -2,
                    "yaw": -100,
                    "targetScene": "lobby",
                    "text": "Back to Lobby",
                    "prompt": "Return to the lobby",
                }
            ],
        },
    },
}


def get_default_tour() -> dict:
    """Return a deep copy of the default tour payload."""
    return copy.deepcopy(_DEFAULT_TOUR)


def get_empty_tour() -> dict:
    """Return a new empty tour payload used at app startup."""
    return {
        "meta": {
            "name": "Untitled Tour",
            "startScene": None,
        },
        "scenes": {},
    }
