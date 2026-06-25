"""
Converts SemanticLayerBuilding.json into isr_knowledge.json (RAG knowledge base).

Merges building room data with static system-level entries (GUIDA purpose, wifi, etc.)
Output is consumed by KnowledgeRetriever which embeds each entry at startup.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent

# ── English translations for room names and types ─────────────────────────────
NAME_EN = {
    "Hall de Entrada":                  "Entrance Hall",
    "Contabilidade e Secretaria":       "Accounting and Secretary Office",
    "Gabinete 0.10":                    "Office 0.10",
    "Oficina Serralharia":              "Metalwork Workshop",
    "Elevador - Zona T":                "Elevator Zone T",
    "Escadas - Zona T":                 "Stairs Zone T",
    "Laboratorio de Mecatronica":       "Mechatronics Laboratory",
    "WC Homens":                        "Men's Restroom",
    "Exterior ISR":                     "ISR Outdoor Area",
    "Escadas - Zona S":                 "Stairs Zone S",
    "Elevador - Zona S":                "Elevator Zone S",
    "Projectos":                        "Projects Room",
    "Biblioteca":                       "Library",
    "Escadas - Zona A":                 "Stairs Zone A",
    "Elevador - Zona A":                "Elevator Zone A",
    "WC Mulheres":                      "Women's Restroom",
    "Bar":                              "Bar / Cafeteria",
    "Anfiteatro":                       "Auditorium",
    "Sala de Reuniões":                 "Meeting Room",
    "Gabinete 0.22":                    "Office 0.22",
    "Gabinete 0.21":                    "Office 0.21",
    "Gabinete 0.20":                    "Office 0.20",
    "Gabinete 0.19":                    "Office 0.19",
    "Gabinete 0.18":                    "Office 0.18",
    "Gabinete 0.16":                    "Office 0.16",
    "Gabinete 0.15":                    "Office 0.15",
    "Gabinete 0.14":                    "Office 0.14",
    "Gabinete 0.13":                    "Office 0.13",
    "Gabinete 0.12":                    "Office 0.12",
    "Laboratorio de Robotica Movel":    "Mobile Robotics Laboratory",
    "Laboratorio de Visao Computacional": "Computer Vision Laboratory",
    "Laboratorio de Automacao":         "Automation Laboratory",
}

DESC_EN = {
    "R001": "The main entrance area of the ISR building with two sofas for visitors and staff.",
    "R002": "Administrative office handling secretary and accounting activities.",
    "R003": "Researcher office for individual use.",
    "R004": "Metalwork and fabrication workshop for mechanical projects.",
    "E05":  "Elevator providing access to floors 1 and 2 (Zone T).",
    "E06":  "Staircase providing access to floors 1 and 2 (Zone T). Open 24 hours.",
    "R007": "Mechatronics laboratory for robotics and automation projects.",
    "R008": "Men's restroom on the ground floor.",
    "R009": "ISR outdoor garden area where you can eat, rest, or take a break.",
    "E10":  "Staircase providing access to floors 1 and 2 (Zone S).",
    "E11":  "Elevator providing access to floors 1 and 2 (Zone S).",
    "R012": "Project development room for researchers and students.",
    "R013": "ISR library with academic resources and reading space.",
    "E14":  "Staircase providing access to floors 1 and 2 (Zone A).",
    "E15":  "Elevator providing access to floors 1 and 2 (Zone A).",
    "R016": "Women's restroom on the ground floor.",
    "R040": "Bar and cafeteria serving coffee, tea, and light meals.",
    "R017": "Auditorium with seating for up to 495 people, configurable to 200. Has a projector and WiFi.",
    "R018": "Meeting room for project meetings, seminars, and events.",
    "R019": "Researcher office 0.22.",
    "R020": "Researcher office 0.21.",
    "R021": "Researcher office 0.20.",
    "R022": "Researcher office 0.19.",
    "R023": "Researcher office 0.18.",
    "R024": "Researcher office 0.16.",
    "R025": "Researcher office 0.15.",
    "R026": "Researcher office 0.14.",
    "R027": "Researcher office 0.13.",
    "R028": "Researcher office 0.12.",
    "R031": "Mobile Robotics Laboratory for research in autonomous mobile systems.",
    "R032": "Computer Vision Laboratory for image processing and visual perception research.",
    "R033": "Automation Laboratory for control systems and industrial automation research.",
}

HOURS_EN = {
    "Aberto 24 horas":                                          "Open 24 hours",
    "Aberto pelas 9:00 às 13:00, e das 14:00 às 17:00":        "Open 09:00–13:00 and 14:00–17:00",
}

CATEGORY = {
    "R001": "location", "R002": "office",   "R003": "office",
    "R004": "lab",      "E05":  "transit",  "E06":  "transit",
    "R007": "lab",      "R008": "facility", "R009": "facility",
    "E10":  "transit",  "E11":  "transit",  "R012": "room",
    "R013": "library",  "E14":  "transit",  "E15":  "transit",
    "R016": "facility", "R040": "cafeteria","R017": "room",
    "R018": "room",     "R019": "office",   "R020": "office",
    "R021": "office",   "R022": "office",   "R023": "office",
    "R024": "office",   "R025": "office",   "R026": "office",
    "R027": "office",   "R028": "office",   "R031": "lab",
    "R032": "lab",      "R033": "lab",
}

# ── Static system-level entries (kept from original KB) ───────────────────────
SYSTEM_ENTRIES = [
    {
        "id": "guida_purpose",
        "text": (
            "GUIDA is an intelligent building assistant robot deployed at ISR "
            "(Institute of Systems and Robotics), University of Coimbra. "
            "It answers questions about the building, guides visitors to rooms, "
            "and provides information about labs and staff. It works fully offline."
        ),
        "category": "system",
    },
    {
        "id": "isr_overview",
        "text": (
            "ISR (Instituto de Sistemas e Robótica) is a research institute at the "
            "University of Coimbra focused on robotics, automation, computer vision, "
            "and intelligent systems. The building is on the Polo II campus."
        ),
        "category": "system",
    },
    {
        "id": "building_access",
        "text": (
            "The ISR building is open to researchers, students, and staff. "
            "General building hours are Monday to Friday 09:00–17:00. "
            "The entrance hall is accessible 24 hours. "
            "Some areas require a keycard or prior authorisation."
        ),
        "category": "schedule",
    },
    {
        "id": "wifi",
        "text": (
            "WiFi is available throughout the ISR building. "
            "Staff and students use the Eduroam network. "
            "The auditorium (R017) also has WiFi for events."
        ),
        "category": "facilities",
    },
    {
        "id": "restrooms",
        "text": (
            "There are two restrooms on the ground floor: "
            "the Men's Restroom (WC Homens, R008) and the Women's Restroom (WC Mulheres, R016)."
        ),
        "category": "facilities",
    },
    {
        "id": "vertical_access",
        "text": (
            "The ISR building has three elevator and staircase zones to reach floors 1 and 2: "
            "Zone T (elevator E05, stairs E06), Zone S (elevator E11, stairs E10), "
            "and Zone A (elevator E15, stairs E14). "
            "Stairs in Zone T are open 24 hours; others follow building hours."
        ),
        "category": "transit",
    },
    {
        "id": "laboratories",
        "text": (
            "The ISR ground floor has three research laboratories: "
            "the Mobile Robotics Laboratory (R031), the Computer Vision Laboratory (R032), "
            "and the Automation Laboratory (R033). "
            "There is also a Mechatronics Laboratory (R007). "
            "All labs are open to researchers, students and staff during building hours."
        ),
        "category": "lab",
    },
    {
        "id": "cafeteria_bar",
        "text": (
            "The Bar / Cafeteria (R040) is on the ground floor and serves coffee, tea, "
            "and light meals. Open 09:00–13:00 and 14:00–17:00 on weekdays."
        ),
        "category": "cafeteria",
    },
    {
        "id": "library",
        "text": (
            "The ISR Library (R013, Biblioteca) is on the ground floor. "
            "It contains academic resources and reading space. "
            "Open 09:00–13:00 and 14:00–17:00. Access for researchers, students and staff."
        ),
        "category": "library",
    },
    {
        "id": "auditorium",
        "text": (
            "The Auditorium (R017, Anfiteatro) can seat up to 495 people and is configurable "
            "for 200 seats. It has a projector and WiFi. Used for lectures, seminars, and events. "
            "Open 09:00–13:00 and 14:00–17:00."
        ),
        "category": "room",
    },
    {
        "id": "meeting_room",
        "text": (
            "The Meeting Room (R018, Sala de Reuniões) is available for project meetings, "
            "seminars, and events. Open 09:00–13:00 and 14:00–17:00."
        ),
        "category": "room",
    },
    {
        "id": "secretary",
        "text": (
            "The Accounting and Secretary Office (R002, Contabilidade e Secretaria) handles "
            "administrative tasks. Staffed by Maria José. "
            "Open 09:00–13:00 and 14:00–17:00."
        ),
        "category": "office",
    },
]


def build_room_entry(room: dict) -> dict:
    rid   = room["id"]
    name  = NAME_EN.get(room["name"], room["name"])
    desc  = DESC_EN.get(rid, room.get("description", ""))
    hours = HOURS_EN.get(room.get("open", ""), room.get("open", ""))
    cat   = CATEGORY.get(rid, "room")

    parts = [f"{name} (room {rid}, floor {room['floor']}): {desc}"]
    if hours:
        parts.append(f"Hours: {hours}.")
    if room.get("capacity") and room["capacity"] > 0:
        parts.append(f"Capacity: {room['capacity']} people.")
    if room.get("occupant") and room["occupant"] not in ("Alunos e Professores", "utilizadores dos pisos"):
        parts.append(f"Contact / occupant: {room['occupant']}.")

    return {"id": rid, "text": " ".join(parts), "category": cat}


def main():
    semantic = json.loads((HERE / "SemanticLayerBuilding.json").read_text(encoding="utf-8"))

    room_entries = [build_room_entry(r) for r in semantic]

    all_entries = SYSTEM_ENTRIES + room_entries

    out_path = HERE / "isr_knowledge.json"
    out_path.write_text(json.dumps(all_entries, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Written {len(all_entries)} entries to {out_path.name}")
    print(f"  System entries : {len(SYSTEM_ENTRIES)}")
    print(f"  Room entries   : {len(room_entries)}")
    print()
    for e in all_entries:
        print(f"  [{e['id']:<30}] {e['text'][:80]}…")


if __name__ == "__main__":
    main()
