from ..base import BaseRulesEngine
from .intent import RestaurantIntentClassifier
from .state import RestaurantState

class RestaurantRulesEngine(BaseRulesEngine):
    def __init__(self):
        self.intent_classifier = RestaurantIntentClassifier()
        self.menu = self.intent_classifier.menu_items

    def process(self, user_text: str, state: RestaurantState) -> dict:
        intent = self.intent_classifier.classify(user_text)
        entities = self.intent_classifier.extract_entities(user_text)

        # ========== GREETING STAGE ==========
        if state.stage == "greeting":
            if intent in ["order", "menu"]:
                state.stage = "ordering"
                return {"action": "show_menu", "data": {"menu": self.menu}}
            else:
                return {"action": "greet", "data": {}}

        # ========== ORDERING STAGE ==========
        elif state.stage == "ordering":
            # Adding/removing items
            if intent == "remove_item" and entities.get("item"):
                state.remove_item(entities["item"])
                return {"action": "item_removed", "data": {"item": entities["item"], "order": state.current_order, "total": state.total_price()}}
            elif entities.get("item"):
                item = entities["item"]
                qty = entities.get("quantity", 1)
                state.add_item(item, qty)
                return {"action": "item_added", "data": {"item": item, "qty": qty, "order": state.current_order, "total": state.total_price()}}
            elif intent == "menu":
                return {"action": "show_menu", "data": {"menu": self.menu}}
            elif intent == "confirm":
                if state.current_order:
                    state.stage = "confirming"
                    return {"action": "ask_confirmation", "data": {"order": state.current_order, "total": state.total_price()}}
                else:
                    return {"action": "empty_order", "data": {}}
            elif intent == "cancel":
                state.reset()
                return {"action": "order_cancelled", "data": {}}
            else:
                return {"action": "ask_item", "data": {}}

        # ========== CONFIRMING STAGE ==========
        elif state.stage == "confirming":
            if intent == "confirm":
                state.confirmed = True
                state.stage = "payment"
                return {"action": "order_confirmed", "data": {"order": state.current_order, "total": state.total_price()}}
            elif intent == "cancel":
                state.reset()
                return {"action": "order_cancelled", "data": {}}
            else:
                return {"action": "ask_confirmation_again", "data": {"order": state.current_order, "total": state.total_price()}}

        # ========== PAYMENT STAGE ==========
        elif state.stage == "payment":
            if intent == "ask_bill":
                return {"action": "show_bill", "data": {"order": state.current_order, "total": state.total_price()}}
            else:
                return {"action": "ask_payment", "data": {}}

        return {"action": "unknown", "data": {}}