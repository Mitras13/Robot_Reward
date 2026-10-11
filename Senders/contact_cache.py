# -*- coding: utf-8 -*-
"""
contact_cache.py - جدول محلی مخاطبین (اسم -> id) برای پیام‌رسان داخلی.

هر بار که با اسم سرچ می‌کنیم و یه نتیجه‌ی یکتا پیدا می‌شه، اینجا ذخیره می‌شه
تا دفعه‌ی بعد نیازی به سرچ دوباره (رفت‌وبرگشت شبکه‌ای) نباشه - مستقیم از
روی کش، id رو می‌گیریم و می‌فرستیم.
"""

import json
import os

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contacts_cache.json")


def _normalize(name: str) -> str:
    return name.strip()


def load() -> dict:
    if not os.path.isfile(CACHE_PATH):
        return {}
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save(cache: dict):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def get(name: str) -> dict | None:
    cache = load()
    return cache.get(_normalize(name))


def put(name: str, username: str, alias: str, is_entity: bool, is_deactive: bool = False):
    cache = load()
    cache[_normalize(name)] = {
        "username": username, "alias": alias, "is_entity": is_entity, "is_deactive": is_deactive,
    }
    save(cache)


def mark_deactive(username_or_key: str):
    """وقتی از پاسخ سرور (NOT_PERMITTED) می‌فهمیم یه مقصد دائماً غیرقابل‌ارسال
    شده، هرجای کش که این username رو داره (چه کلید چه مقدار) علامت می‌زنیم
    تا دیگه هیچ‌وقت دوباره تلاش نشه"""
    cache = load()
    changed = False
    for key, entry in cache.items():
        if key == username_or_key or entry.get("username") == username_or_key:
            if not entry.get("is_deactive"):
                entry["is_deactive"] = True
                changed = True
    if changed:
        save(cache)


def remove(name: str):
    cache = load()
    if _normalize(name) in cache:
        del cache[_normalize(name)]
        save(cache)


def list_all() -> dict:
    return load()


# کش SessionId (نه id/username - این "شناسه‌ی مکالمه" با یه مخاطبه، لازم برای
# clear_msg_history). کلید این بخش با username (نه اسم نمایشی/سرچ‌شده) است -
# چون یه username ممکنه از چند اسم مختلف سرچ شده باشه، ولی SessionId فقط به
# username واقعی مربوطه. تو یه بخش جدا ("__sessions__") داخل همون فایل کش
# نگه‌داری می‌شه تا فایل جدیدی لازم نباشه.
_SESSIONS_KEY = "__sessions__"


def get_session(username: str):
    cache = load()
    return cache.get(_SESSIONS_KEY, {}).get(username)


def put_session(username: str, session_id):
    cache = load()
    sessions = cache.setdefault(_SESSIONS_KEY, {})
    sessions[username] = session_id
    save(cache)
