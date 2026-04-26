from ..base import BaseState

class RestaurantState(BaseState):
    def __init__(self):
        super().__init__()
        self.order_items = None          # dict {item: quantity} (or just item name)
        self.name = None
        self.phone = None
        self.delivery_preference = None  # "delivery" or "takeaway"
        self.confirmed = False
        self.required_fields = ["order_items", "name", "phone", "delivery_preference"]

    def reset(self):
        self.__init__()

    def is_complete(self):
        return self.confirmed and self.order_items and self.name and self.phone and self.delivery_preference

    def total_price(self):
        # Implement based on menu; for now return a placeholder
        # You can calculate from self.order_items later
        return 350

    def to_dict(self):
        return {
            "order": self.order_items,
            "name": self.name,
            "phone": self.phone,
            "delivery_preference": self.delivery_preference
        }