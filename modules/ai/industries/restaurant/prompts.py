from ..base import BasePrompts

class RestaurantPrompts(BasePrompts):
    def __init__(self, org_id: str = None):
        self.org_id = org_id

    def get_system_prompt(self) -> str:
        from modules.ai.agent import get_system_prompt_sync
        base = get_system_prompt_sync(self.org_id)
        json_instruction = """
IMPORTANT: After EVERY response, output a JSON object on its own line exactly like this:

{"intent": "ask_item|ask_name|ask_phone|ask_delivery|confirm", "entities": {"order_items": "...", "name": "...", "phone": "...", "delivery_preference": "delivery/takeaway"}, "lead": {"lead": true/false, "interest": "...", "service": "...", "score": 0-100}}

If no lead is detected, set "lead": {"lead": false, "interest": "", "service": "", "score": 0}. Do not omit the "lead" field.
"""
        return base + json_instruction

    def get_action_prompt(self, action: str, data: dict) -> str:
        if action == "greet":
            return "Namaste! Welcome to our restaurant. Would you like to see the menu or place an order?"
        elif action == "show_menu":
            menu = data.get("menu", {})
            lines = ["Here's our menu with prices:\n"]
            for item, price in menu.items():
                lines.append(f"• {item.title()} – ₹{price}")
            lines.append("\nWhat would you like to order? Just say the dish name (e.g., 'paneer butter masala').")
            return "\n".join(lines)
        elif action == "item_added":
            item = data["item"].title()
            qty = data["qty"]
            total = data["total"]
            return f"Added {qty} {item}(s). Your current total is ₹{total}. Anything else? (Say 'confirm' to place order, 'menu' to see again, or 'cancel' to clear.)"
        elif action == "item_removed":
            item = data["item"].title()
            total = data["total"]
            return f"Removed {item}. Your order total is now ₹{total}. Want to add something else?"
        elif action == "ask_item":
            return "What would you like to order? Just say the dish name."
        elif action == "empty_order":
            return "You haven't ordered anything yet. Would you like to see the menu?"
        elif action == "ask_confirmation":
            order_lines = [f"{qty}x {item.title()}" for item, qty in data["order"].items()]
            total = data["total"]
            return f"Your order: {', '.join(order_lines)}. Total ₹{total}. Please confirm by saying 'yes' or 'no'."
        elif action == "ask_confirmation_again":
            order_lines = [f"{qty}x {item.title()}" for item, qty in data["order"].items()]
            total = data["total"]
            return f"Just to confirm, your order is {', '.join(order_lines)}. Total ₹{total}. Say 'yes' to place order or 'no' to cancel."
        elif action == "order_confirmed":
            order_lines = [f"{qty}x {item.title()}" for item, qty in data["order"].items()]
            total = data["total"]
            return f"Great! Your order ({', '.join(order_lines)}) has been placed. Total ₹{total}. Would you like to see the bill or pay now?"
        elif action == "order_cancelled":
            return "Order cancelled. You can start a new order anytime."
        elif action == "show_bill":
            order_lines = [f"{qty}x {item.title()} – ₹{self._get_price(item) * qty}" for item, qty in data["order"].items()]
            total = data["total"]
            return "Here's your bill:\n" + "\n".join(order_lines) + f"\nTotal: ₹{total}\nThank you! Please pay at the counter."
        elif action == "ask_payment":
            return "Would you like to see your bill or continue ordering?"
        else:
            return "How can I help you with your order?"

    def _get_price(self, item: str) -> int:
        from .intent import RestaurantIntentClassifier
        return RestaurantIntentClassifier().menu_items.get(item, 0)