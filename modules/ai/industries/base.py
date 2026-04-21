from abc import ABC, abstractmethod

class BaseIntentClassifier(ABC):
    @abstractmethod
    def classify(self, text: str) -> str:
        pass
    @abstractmethod
    def extract_entities(self, text: str) -> dict:
        pass

class BaseState(ABC):
    def __init__(self):
        self.required_fields = []   # list of field names that must be set for completion
        self.confirmed = False

    @abstractmethod
    def is_complete(self) -> bool:
        """Check if all required fields are set."""
        return all(getattr(self, field, None) for field in self.required_fields)

    def reset(self):
        self.__init__()

class BaseRulesEngine(ABC):
    def __init__(self):
        self.required_fields = []   # must be set in child class

    def process_confirmation(self, user_text: str, state: BaseState):
        """Generic confirmation logic. Returns action if state is complete."""
        if state.is_complete() and not state.confirmed:
            if any(word in user_text.lower() for word in ["yes", "haan", "confirm", "theek", "ok", "book", "done"]):
                state.confirmed = True
                return {"action": "confirm_booking", "data": {"state": state.to_dict()}}
            else:
                return {"action": "ask_confirmation", "data": {"state": state.to_dict()}}
        return None

    @abstractmethod
    def process(self, user_text: str, state: BaseState) -> dict:
        """Industry-specific logic. Should call self.process_confirmation after filling fields."""
        pass

class BasePrompts(ABC):
    @abstractmethod
    def get_system_prompt(self) -> str:
        pass
    @abstractmethod
    def get_action_prompt(self, action: str, data: dict) -> str:
        pass