import importlib
from groq import Groq
from sqlalchemy import text
from modules.common.config import GROQ_API_KEY
from modules.common.database import sync_engine
from modules.ai.rag import search_knowledge
from modules.ai.booking_helper import save_booking_generic

client = Groq(api_key=GROQ_API_KEY)
DEFAULT_MODEL = "llama-3.3-70b-versatile"

_agent_cache = {}

def get_primary_prompt_for_org(org_id: str) -> str:
    with sync_engine.connect() as conn:
        result = conn.execute(
            text("SELECT prompt_text FROM organization_prompts WHERE organization_id = :org_id AND is_primary = true"),
            {"org_id": org_id}
        )
        row = result.fetchone()
        if row:
            return row[0]
    return None

def get_system_prompt_sync(org_id: str = None) -> str:
    # First try to get the primary prompt from new table
    if org_id:
        primary = get_primary_prompt_for_org(org_id)
        if primary:
            return primary
    # Fallback to old ai_configurations table
    with sync_engine.connect() as conn:
        if org_id:
            result = conn.execute(
                text("SELECT system_prompt FROM ai_configurations WHERE organization_id = :org_id"),
                {"org_id": org_id}
            )
            row = result.fetchone()
            if row and row[0] and row[0].strip():
                return row[0]
        result = conn.execute(
            text("SELECT system_prompt FROM ai_configurations WHERE organization_id IS NULL")
        )
        row = result.fetchone()
        if row and row[0] and row[0].strip():
            return row[0]
    return "You are a helpful AI assistant for a small business. Answer concisely and politely."


def get_industry_module(org_id: str):
    with sync_engine.connect() as conn:
        result = conn.execute(
            text("SELECT business_type FROM organizations WHERE id = :org_id"),
            {"org_id": org_id}
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Organization {org_id} not found")
        industry = row[0].lower() if row[0] else "salon"
    try:
        module = importlib.import_module(f"modules.ai.industries.{industry}")
        return module
    except ImportError:
        return None

class DefaultAgent:
    def __init__(self, user_id: str, org_id: str = None):
        self.user_id = user_id
        self.org_id = org_id
        self.memory = []

    def predict(self, user_input: str) -> str:
        if not user_input or not user_input.strip():
            return "Kya baat hai? Please type again."
        system_prompt = get_system_prompt_sync(self.org_id)
        history = "\n".join([f"Customer: {m['user']}\nAssistant: {m['bot']}" for m in self.memory[-5:]])
        full_prompt = f"{system_prompt}\n\n{history}\nCustomer: {user_input}\nAssistant:"
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.7,
                max_tokens=250
            )
            reply = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Groq error: {e}")
            reply = "Sorry, I'm having trouble. Please try again."
        self.memory.append({"user": user_input, "bot": reply})
        return reply

class SmartAgent:
    def __init__(self, user_id: str, org_id: str = None):
        self.user_id = user_id
        self.org_id = org_id
        self.memory = []
        self.industry_mod = None
        self.prompts = None
        self.rules = None
        self.state = None
        self._fallback = False

        if org_id:
            self.industry_mod = get_industry_module(org_id)
            if self.industry_mod:
                required = ['IntentClassifier', 'RulesEngine', 'State', 'Prompts']
                missing = [cls for cls in required if not hasattr(self.industry_mod, cls)]
                if missing:
                    print(f"Industry module missing {missing}, falling back to DefaultAgent")
                    self._fallback = True
                    self.default_agent = DefaultAgent(user_id, org_id)
                    return
                self.intent = self.industry_mod.IntentClassifier()
                self.rules = self.industry_mod.RulesEngine()
                self.state = self.industry_mod.State()
                self.prompts = self.industry_mod.Prompts(org_id)
                self._fallback = False
            else:
                print(f"No industry module for org {org_id}, using DefaultAgent")
                self._fallback = True
                self.default_agent = DefaultAgent(user_id, org_id)
        else:
            self._fallback = True
            self.default_agent = DefaultAgent(user_id, org_id)

    def predict(self, user_input: str) -> str:
        if self._fallback:
            return self.default_agent.predict(user_input)

        if not user_input or not user_input.strip():
            return "Kya baat hai? Please type again."

        try:
            action_data = self.rules.process(user_input, self.state)
            action = action_data["action"]
        except Exception as e:
            print(f"Rules engine error: {e}, falling back to default")
            return self.default_agent.predict(user_input)

        # Handle confirmation (generic)
        if action == "confirm_booking":
            save_booking_generic(self.org_id, self.state, self.industry_mod.__name__.split('.')[-1])
            action_prompt = "Booking confirmed. Say: 'Booking confirmed! We'll remind you one day before.'"
        else:
            action_prompt = self.prompts.get_action_prompt(action, action_data.get("data", {}))

        context = ""
        if self.org_id:
            chunks = search_knowledge(self.org_id, user_input, k=2)
            if chunks:
                context = "\n\nInfo: " + "\n".join(chunks)

        history = "\n".join([f"Customer: {m['user']}\nBot: {m['bot']}" for m in self.memory[-5:]])
        full_prompt = f"{self.prompts.get_system_prompt()}\n{context}\n\n{history}\nCustomer: {user_input}\nRules say: {action_prompt}\nBot:"

        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.5,
                max_tokens=250
            )
            reply = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Groq error: {e}")
            reply = "Sorry, I'm having trouble. Please try again."

        self.memory.append({"user": user_input, "bot": reply})
        return reply

def get_agent_for_user_compat(user_id: str, org_id: str = None):
    key = f"{user_id}_{org_id}"
    if key not in _agent_cache:
        _agent_cache[key] = SmartAgent(user_id, org_id)
    return _agent_cache[key]