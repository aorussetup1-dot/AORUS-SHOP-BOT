import json
import os

USERS_DB = "users.json"
PENDING_DB = "pending.json"
KEYS_DB = "keys.json"


# ---------------- UTIL ----------------
def _load(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)


def _save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)


# ---------------- USERS ----------------
def get_user(user_id: int):
    db = _load(USERS_DB)
    uid = str(user_id)

    if uid not in db:
        db[uid] = {"balance": 0}
        _save(USERS_DB, db)

    return db[uid]


def add_balance(user_id: int, amount: int):
    db = _load(USERS_DB)
    uid = str(user_id)

    if uid not in db:
        db[uid] = {"balance": 0}

    db[uid]["balance"] += amount
    _save(USERS_DB, db)


# backward compatibility
def update_balance(user_id: int, amount: int):
    add_balance(user_id, amount)


# ---------------- KEYS ----------------
def get_key(duration: str):
    """
    duration = '1', '7', '30'
    """
    keys_db = _load(KEYS_DB)

    if duration not in keys_db:
        return None

    if not keys_db[duration]:
        return None

    key = keys_db[duration].pop(0)
    _save(KEYS_DB, keys_db)

    return key


def load_json(file):
    return _load(file)


def save_keys(data):
    _save(KEYS_DB, data)


# ---------------- PENDING PAYMENTS ----------------
def create_pending(txn_id: str, user_id: int, amount: int):
    db = _load(PENDING_DB)
    db[txn_id] = {
        "user_id": user_id,
        "amount": amount
    }
    _save(PENDING_DB, db)


def get_pending(txn_id: str):
    db = _load(PENDING_DB)
    return db.get(txn_id)


def delete_pending(txn_id: str):
    db = _load(PENDING_DB)
    if txn_id in db:
        del db[txn_id]
        _save(PENDING_DB, db)
