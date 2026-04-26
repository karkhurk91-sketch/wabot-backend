from ..base import BaseRulesEngine
from .intent import RestaurantIntentClassifier
from .state import RestaurantState
import re

class RestaurantRulesEngine(BaseRulesEngine):
    def __init__(self):
        super().__init__()

    def process(self, user_text: str, state: RestaurantState) -> dict:
        print(f"\n=== DEBUG: processing user text: '{user_text}' ===")
        user_lower = user_text.lower()

        # Extract item
        if not state.order_items:
            classifier = RestaurantIntentClassifier()
            entities = classifier.extract_entities(user_text)
            if entities.get("item"):
                state.order_items = {entities["item"]: 1}
                print(f"DEBUG: extracted order_items = {state.order_items}")

        # Extract name
        if not state.name:
            # Multiple patterns
            patterns = [
                r"(?:name is|i am|my name is|i'm)\s+(\w+)",
                r"(\w+)\s*(?:here|speaking)",
                r"^(?:this is|i am)\s+(\w+)",
                r"my name is (\w+)",
                r"i'?m (\w+)"
            ]
            for pat in patterns:
                match = re.search(pat, user_lower)
                if match:
                    state.name = match.group(1).title()
                    print(f"DEBUG: extracted name = {state.name}")
                    break
            # If still no name, the entire message might be just a name
            if not state.name and len(user_text.split()) <= 2:
                potential_name = user_text.strip().title()
                if potential_name.isalpha():
                    state.name = potential_name
                    print(f"DEBUG: assumed name = {state.name}")

        # Extract phone
        if not state.phone:
            nums = re.findall(r"\b\d{10}\b", user_text)
            if nums:
                state.phone = nums[0]
                print(f"DEBUG: extracted phone = {state.phone}")

        # Extract delivery preference
        if not state.delivery_preference:
            if "delivery" in user_lower:
                state.delivery_preference = "delivery"
                print("DEBUG: set delivery_preference = delivery")
            elif "takeaway" in user_lower or "pickup" in user_lower:
                state.delivery_preference = "takeaway"
                print("DEBUG: set delivery_preference = takeaway")

        # Determine missing fields
        missing = []
        if not state.order_items:
            missing.append("order")
        if not state.name:
            missing.append("name")
        if not state.phone:
            missing.append("phone")
        if not state.delivery_preference:
            missing.append("delivery")

        print(f"DEBUG: current state -> order={state.order_items}, name={state.name}, phone={state.phone}, delivery={state.delivery_preference}, confirmed={state.confirmed}")
        print(f"DEBUG: missing fields: {missing}")

        if not missing:
            if not state.confirmed:
                if any(word in user_lower for word in ["yes", "haan", "confirm", "theek", "ok", "book", "done"]):
                    state.confirmed = True
                    print("DEBUG: confirmation detected -> returning confirm_booking")
                    return {"action": "confirm_booking", "data": {"state": state.to_dict()}}
                else:
                    print("DEBUG: all fields collected, waiting for confirmation")
                    return {"action": "ask_confirmation", "data": {"order": state.order_items, "total": state.total_price()}}
            else:
                return {"action": "already_confirmed", "data": {}}
        else:
            # Ask for first missing field
            if "order" in missing:
                return {"action": "ask_item", "data": {}}
            if "name" in missing:
                return {"action": "ask_name", "data": {}}
            if "phone" in missing:
                return {"action": "ask_phone", "data": {}}
            if "delivery" in missing:
                return {"action": "ask_delivery_preference", "data": {}}
        return {"action": "unknown", "data": {}}