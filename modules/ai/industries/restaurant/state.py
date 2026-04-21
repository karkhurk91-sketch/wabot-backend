from ..base import BaseState

class RestaurantState(BaseState):
    def __init__(self):
        self.current_order = {}      # {item_name: quantity}
        self.stage = "greeting"      # greeting, ordering, confirming, payment
        self.last_item = None
        self.confirmed = False

    def reset(self):
        self.__init__()

    def is_complete(self):
        return self.confirmed and self.current_order

    def add_item(self, item: str, quantity: int = 1):
        self.current_order[item] = self.current_order.get(item, 0) + quantity
        self.last_item = item

    def remove_item(self, item: str):
        if item in self.current_order:
            del self.current_order[item]

    def update_quantity(self, item: str, quantity: int):
        if quantity <= 0:
            self.remove_item(item)
        else:
            self.current_order[item] = quantity

    def total_price(self):
        from .intent import RestaurantIntentClassifier
        classifier = RestaurantIntentClassifier()
        return sum(classifier.menu_items.get(item, 0) * qty for item, qty in self.current_order.items())

    def to_dict(self):
        return {
            "order": self.current_order,
            "total": self.total_price(),
            "stage": self.stage,
            "confirmed": self.confirmed
        }