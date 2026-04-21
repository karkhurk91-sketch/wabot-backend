from ..base import BasePrompts

class SalonPrompts(BasePrompts):
    def __init__(self, org_id: str = None):
        self.org_id = org_id

    def get_system_prompt(self) -> str:
        # Import here to avoid circular import
        from modules.ai.agent import get_system_prompt_sync
        return get_system_prompt_sync(self.org_id)

    def get_action_prompt(self, action: str, data: dict) -> str:
        if action == "ask_service":
            return "Customer wants to book. Ask: 'Aaj kya service chahiye? Haircut, facial, waxing?'"
        elif action == "ask_time":
            slots = ", ".join(data.get("suggestions", ["11 AM", "2 PM", "5 PM"]))
            return f"Ask for preferred time. Slots: {slots}. If invalid, say 'Sorry, that time not available. Please choose from {slots}'."
        elif action == "invalid_time":
            slots = ", ".join(data.get("suggestions", ["11 AM", "2 PM", "5 PM"]))
            return f"Customer gave invalid time. Say 'Sorry, not available. Please choose {slots}'."
        elif action == "ask_name":
            return "Ask: 'Accha, aapka naam kya hai?'"
        elif action == "ask_phone":
            return "Ask: 'Phone number batao, confirmation bhejenge.'"
        elif action == "confirm":
            d = data["state"]
            return f"Confirm booking: '{d['service']} at {d['time']} for {d['name']} (phone {d['phone']})'. Say: 'Booking confirm! Hum remind karenge. Aur kuch?'"
        else:
            return "Respond politely and helpfully."