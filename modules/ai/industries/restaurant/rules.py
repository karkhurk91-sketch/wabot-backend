# modules/ai/industries/restaurant/rules.py
from ..base import BaseRulesEngine
from .state import RestaurantState

class RestaurantRulesEngine(BaseRulesEngine):
    def process(self, user_text: str, state: RestaurantState) -> dict:
        # We rely on the prompt to collect fields. This rules engine just returns
        # the next action based on missing fields, but the AI will fill them.
        missing = []
        if not state.order_items:
            missing.append("order")
        if not state.name:
            missing.append("name")
        if not state.phone:
            missing.append("phone")
        if not state.delivery_preference:
            missing.append("delivery")

        if not missing:
            if not state.confirmed:
                if any(word in user_text.lower() for word in ["yes", "confirm", "place order"]):
                    state.confirmed = True
                    return {"action": "confirm_booking", "data": {"state": state.to_dict()}}
                else:
                    return {"action": "ask_confirmation", "data": {}}
            else:
                return {"action": "already_confirmed", "data": {}}
        else:
            # Ask for the first missing field
            if "order" in missing: return {"action": "ask_item", "data": {}}
            if "name" in missing: return {"action": "ask_name", "data": {}}
            if "phone" in missing: return {"action": "ask_phone", "data": {}}
            if "delivery" in missing: return {"action": "ask_delivery_preference", "data": {}}
        return {"action": "unknown", "data": {}}