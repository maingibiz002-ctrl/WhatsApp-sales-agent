session_db = {}

def get_history(sender_id: str) -> list:
    if sender_id not in session_db:
        session_db[sender_id] = []
    return session_db[sender_id]

def add_message(sender_id: str, role: str, content: str):
    history = get_history(sender_id)
    history.append({"role": role, "content": content})
    if len(history) > 10:
        session_db[sender_id] = history[-10:]