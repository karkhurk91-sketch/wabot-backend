# modules/ai/industries/restaurant/intent.py
import re
from difflib import get_close_matches
from ..base import BaseIntentClassifier

class RestaurantIntentClassifier(BaseIntentClassifier):
    def __init__(self):
        self.intents = {
            "greeting": ["hi", "hello", "namaste", "hey"],
            "order": ["order", "want", "need", "chahiye", "lana", "khana", "mango", "le lo"],
            "menu": ["menu", "kya hai", "options", "dish", "items", "show", "dikhao", "list"],
            "price": ["price", "kitne", "cost", "rate", "paise", "daam", "kitna"],
            "confirm": ["haan", "yes", "theek", "ok", "okay", "confirm", "correct", "sahi", "place order"],
            "cancel": ["nahi", "no", "cancel", "matlab", "change", "hatao", "remove"],
            "add_item": ["add", "extra", "aur", "also", "bhi", "plus"],
            "remove_item": ["remove", "hatao", "delete", "nikalo"],
            "ask_bill": ["bill", "total", "kitna hua", "pay", "payment", "check"],
        }
        self.menu_items = {
            "paneer butter masala": 250,
            "butter chicken": 320,
            "dal makhani": 180,
            "veg biryani": 200,
            "chicken biryani": 280,
            "garlic naan": 40,
            "butter naan": 35,
            "jeera rice": 120,
            "gulab jamun": 60,
            "ice cream": 80,
            "tandoori roti": 25,
            "mix veg": 160,
            "chicken tikka": 300,
        }
        self.item_names = list(self.menu_items.keys())

    def classify(self, text: str) -> str:
        text_lower = text.lower()
        for intent, keywords in self.intents.items():
            if any(kw in text_lower for kw in keywords):
                return intent
        return "unknown"

    def extract_entities(self, text: str) -> dict:
        entities = {}
        text_lower = text.lower()
        # Extract dish name – exact match first, then fuzzy
        found = None
        for dish in self.item_names:
            if dish in text_lower:
                found = dish
                break
        if not found:
            words = text_lower.split()
            for word in words:
                match = get_close_matches(word, self.item_names, n=1, cutoff=0.7)
                if match:
                    found = match[0]
                    break
        if found:
            entities["item"] = found
        # Extract name
        name_match = re.search(r"(?:my name is|i am|i'm|name is)\s+([a-zA-Z]+)", text_lower)
        if name_match:
            entities["name"] = name_match.group(1).title()
        elif len(text_lower.split()) == 1 and text_lower.isalpha() and text_lower not in self.item_names:
            entities["name"] = text_lower.title()
        # Extract phone number
        phone_match = re.search(r"\b(\d{10})\b", text)
        if phone_match:
            entities["phone"] = phone_match.group(1)
        return entities