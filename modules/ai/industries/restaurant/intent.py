import re
from difflib import get_close_matches
from ..base import BaseIntentClassifier

class RestaurantIntentClassifier(BaseIntentClassifier):
    def __init__(self):
        self.intents = {
            "greeting": ["hi", "hello", "namaste", "hey", "good morning", "good evening"],
            "order": ["order", "want", "need", "chahiye", "lana", "khana", "mango", "le lo"],
            "menu": ["menu", "kya hai", "options", "dish", "items", "show", "dikhao", "list"],
            "price": ["price", "kitne", "cost", "rate", "paise", "daam", "kitna"],
            "confirm": ["haan", "yes", "theek", "ok", "okay", "confirm", "correct", "sahi", "place order"],
            "cancel": ["nahi", "no", "cancel", "matlab", "change", "hatao", "remove"],
            "add_item": ["add", "extra", "aur", "also", "bhi", "plus"],
            "remove_item": ["remove", "hatao", "delete", "nikalo"],
            "ask_bill": ["bill", "total", "kitna hua", "pay", "payment", "check"],
        }
        # Menu items with prices (can be extended or loaded from DB)
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
        # Extract dish name (exact or fuzzy match)
        for dish in self.item_names:
            if dish in text_lower:
                entities["item"] = dish
                break
        else:
            words = text_lower.split()
            for word in words:
                match = get_close_matches(word, self.item_names, n=1, cutoff=0.7)
                if match:
                    entities["item"] = match[0]
                    break
        # Extract quantity (numbers followed by piece/plate/order)
        num_match = re.search(r"(\d+)\s*(?:piece|plate|order|pc|nos?|time)", text_lower)
        if num_match:
            entities["quantity"] = int(num_match.group(1))
        else:
            entities["quantity"] = 1
        return entities