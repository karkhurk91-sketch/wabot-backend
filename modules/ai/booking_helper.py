import uuid
from datetime import datetime
from modules.common.database import sync_engine
from sqlalchemy import text

def save_booking_generic(org_id: str, state, industry: str):
    # Map industry state fields to booking table columns
    mapping = {
        "salon": {
            "customer_phone": "phone",
            "customer_name": "name",
            "service": "service",
            "booking_date": lambda: datetime.now().date(),
            "booking_time": lambda: datetime.now().time().replace(hour=14, minute=0)
        },
        # Add other industries as needed
    }
    m = mapping.get(industry, {})
    data = {}
    for db_field, source in m.items():
        if callable(source):
            data[db_field] = source()
        else:
            data[db_field] = getattr(state, source, None)

    with sync_engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO bookings (id, organization_id, customer_phone, customer_name, service, booking_date, booking_time, status)
                VALUES (:id, :org_id, :phone, :name, :service, :date, :time, 'confirmed')
            """),
            {
                "id": uuid.uuid4(),
                "org_id": org_id,
                "phone": data.get("customer_phone"),
                "name": data.get("customer_name"),
                "service": data.get("service"),
                "date": data.get("booking_date", datetime.now().date()),
                "time": data.get("booking_time", datetime.now().time())
            }
        )
        conn.commit()