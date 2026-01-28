from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Text
from urllib.parse import quote_plus

import yaml
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


def google_maps_search_url(query: str) -> str:
    # Simple & reliable (no need for exact lat/lng)
    return f"https://www.google.com/maps?q={quote_plus(query)}"


@dataclass
class Place:
    key: str
    title: str
    query: str
    aliases: List[str]
    url: Optional[str] = None  # optional direct Google Maps short link


class LocationStore:
    """
    Loads places from locations.yml (project root by default).
    Supports:
      - aliases (exact match)
      - 'X-р дотуур байр' -> num_dorm_X
      - 'X-р байр'        -> num_building_X   (X=1..5)
    """
    def __init__(self, file_path: str = "locations.yml") -> None:
        self.file_path = file_path
        self._places: List[Place] = []
        self._alias_to_key: Dict[str, str] = {}

    def load(self) -> None:
        self._places = []
        self._alias_to_key = {}

        if not os.path.exists(self.file_path):
            return

        with open(self.file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        for item in (data.get("places") or []):
            key = str(item.get("key", "")).strip()
            title = str(item.get("title", "")).strip()
            query = str(item.get("query", "")).strip()
            url = str(item.get("url", "")).strip() or None
            aliases = item.get("aliases") or []

            if not (key and title and query):
                continue

            aliases_clean: List[str] = []
            for a in aliases:
                a2 = str(a).strip().lower()
                if a2:
                    aliases_clean.append(a2)
                    self._alias_to_key[a2] = key

            # also map title
            self._alias_to_key[title.lower()] = key

            self._places.append(Place(key=key, title=title, query=query, aliases=aliases_clean, url=url))

    def list_titles(self) -> List[str]:
        return [p.title for p in self._places]

    def _get_by_key(self, key: str) -> Optional[Place]:
        return next((p for p in self._places if p.key == key), None)

    def resolve(self, text: str) -> Optional[Place]:
        t = (text or "").strip().lower()
        if not t:
            return None

        # 1) exact alias match
        k = self._alias_to_key.get(t)
        if k:
            return self._get_by_key(k)

        # 2) dorm match first (avoid conflict with "байр")
        if ("дотуур" in t) or ("dorm" in t) or ("dormitory" in t):
            for n in ["1", "2", "3", "4", "5", "6"]:
                if re.search(rf"(^|\D){n}(\D|$)", t) or (n in t):
                    return self._get_by_key(f"num_dorm_{n}")

        # 3) building match: "2-р байр", "3-р байр" ...
        m = re.search(r"([1-5])\s*[-–]?\s*(р|р\.|дугаар)?\s*байр", t)
        if m:
            n = m.group(1)
            return self._get_by_key(f"num_building_{n}")

        # 4) generic MUIS/NUM mention -> main
        if "муис" in t or "muis" in t or "num" in t:
            return self._get_by_key("num_main")

        return None


STORE = LocationStore("locations.yml")
STORE.load()


class ActionSendLocation(Action):
    def name(self) -> Text:
        return "action_send_location"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # 1) slot -> place
        place_text = tracker.get_slot("place")

        # 2) entity -> place
        if not place_text:
            for ent in (tracker.latest_message.get("entities") or []):
                if ent.get("entity") == "place":
                    place_text = ent.get("value")
                    break

        # 3) fallback -> full message
        if not place_text:
            place_text = tracker.latest_message.get("text") or ""

        normalized = (place_text or "").strip().lower()

        # list command
        if normalized in {"байршлууд", "байршил", "locations", "list", "жагсаалт"}:
            titles = STORE.list_titles()
            if not titles:
                dispatcher.utter_message(text="locations.yml хоосон байна (эсвэл олдсонгүй).")
                return []
            dispatcher.utter_message(text="📍 Байршлын жагсаалт:\n- " + "\n- ".join(titles))
            return []

        place = STORE.resolve(place_text)

        if not place:
            dispatcher.utter_message(
                text="Ямар байршил хэрэгтэй вэ?\nЖишээ: “МУИС, 2-р байр”, “4-р дотуур байр”, эсвэл “байршлууд”."
            )
            return []

        url = place.url or google_maps_search_url(place.query)
        dispatcher.utter_message(text=f"📍 {place.title}\n🗺️ {url}")
        return [SlotSet("place", place.title)]
