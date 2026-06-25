"""
Maps natural language room references to nav stack location IDs.
Add entries here when the navigation team provides new location names.
"""
from typing import Optional

# Keys: lowercase keywords that may appear in user speech
# Values: exact location_name string expected by /set_goal service
LOCATION_MAP: dict[str, str] = {
    "meeting room":         "meeting_room_corridor",
    "meeting":              "meeting_room_corridor",
    "sala de reuniões":     "meeting_room_corridor",
    "cafeteria":            "cafeteria",
    "bar":                  "cafeteria",
    "café":                 "cafeteria",
    "library":              "library",
    "biblioteca":           "library",
    "auditorium":           "auditorium",
    "anfiteatro":           "auditorium",
    "entrance":             "entrance_hall",
    "entrance hall":        "entrance_hall",
    "hall":                 "entrance_hall",
    "laboratory":           "mobile_robotics_lab",
    "robotics lab":         "mobile_robotics_lab",
    "mobile robotics":      "mobile_robotics_lab",
    "computer vision":      "computer_vision_lab",
    "automation lab":       "automation_lab",
    "secretary":            "secretary_office",
    "secretaria":           "secretary_office",
    "docking":              "docking_station",
    "charging":             "docking_station",
    "charge":               "docking_station",
}


def extract_navigation_goal(transcription: str) -> Optional[str]:
    """
    Scan transcription for known location keywords and return the nav stack ID.
    Returns None if no known location is mentioned.
    Longer phrases are checked first to avoid partial matches.
    """
    lowered = transcription.lower()
    for keyword in sorted(LOCATION_MAP, key=len, reverse=True):
        if keyword in lowered:
            return LOCATION_MAP[keyword]
    return None
