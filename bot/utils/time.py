from datetime import datetime, timezone




def get_current_time():
    return datetime.utcnow()  # Возвращает время без tzinfo