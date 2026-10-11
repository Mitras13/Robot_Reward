# === VENDORED FILE - DO NOT EDIT ABOVE THIS BLOCK, READ BEFORE EDITING BELOW ===
# Copied verbatim from Robot_Analytics (sibling project) at commit e08d4f7,
# path Senders/send_message.py. Deliberately diverged since (num_tabs
# default 1405/06/24; full logging/resume rewrite 1405/06/25 - see below) -
# a fix made here does NOT reach Robot_Analytics automatically, and vice
# versa - any real bug fix or improvement found in either copy should be
# ported to the other by hand.
#
# 1405/06/25 (user decision): this copy's own private CSV log
# (C:\SharedAssets\logs\Sent_message_log\send_log.csv) and resume-file
# mechanism were removed entirely in favor of core/runlog.py, a generic
# run/item log shared with Senders/send_message_v2.py (v2) and, later,
# other parts of the project (see core/runlog.py's own docstring). This
# copy is no longer a drop-in file for a project without a core.runlog
# module - an accepted, deliberate consequence, not an oversight.
#
# (tests/test_vendored_sender.py, referenced in earlier versions of this
# header, was never actually created in this project - there is no sha256
# pin test to keep in sync. This header is the only record of deliberate
# vs. accidental drift from the sibling project's copy.)
#
# 1405/07/19 (user decision, deliberate): the hardcoded messenger
# USERNAME/PASSWORD were removed from this file - they are now read from
# Senders/.env (PEZHVA_USERNAME/PEZHVA_PASSWORD, the same account v2 uses).
# The old password is still in git history, so it must be rotated on the
# messenger side; removing it here only stops it spreading further.
# === END VENDORED-FILE HEADER ===

# -*- coding: utf-8 -*-
"""
send_message.py - ارسال گزارش (عکس/متن) به هر کارشناس، با Playwright (Async API)

قرارداد main.py: send_message(rendered, agents_csv_path)
    rendered: خروجی render_target -> [{"contact": نام, "image": مسیر یا None, "caption": متن}, ...]
    agents_csv_path: فعلاً استفاده نمی‌شه (نگه‌داشته شده برای هماهنگی امضا با بقیه‌ی پروژه‌ها)

⚠️ چرا Async API (نه sync + threading):
   نسخه‌ی قبلی این فایل از threading.Thread برای موازی‌سازی استفاده می‌کرد، ولی
   Playwright sync API از داخل خودش با greenlet کار می‌کنه که فقط تو همون Thread
   اصلی معتبره - صدا زدن page/context از یه Thread دیگه با خطای
   "Cannot switch to a different thread" کرش می‌کنه (تست واقعی این رو نشون داد).

   راه‌حل درست: Playwright Async API + asyncio. همه‌چیز تو یه Thread واحد ولی
   concurrent اجرا می‌شه (با asyncio.gather + Semaphore برای محدود کردن تعداد
   تب‌های هم‌زمان به num_tabs) - نه چند Thread واقعی. یه لاگین واحد کافیه، هیچ
   مشکل cross-thread ای هم پیش نمیاد.

⚠️ آخرین مرحله‌ی ارسال واقعی (کلیک روی "تایید" / press Enter) در این نسخه فعاله.

⚠️ محافظ حیاتی امنیتی (open_chat): بعد از باز کردن چت با کلیک روی نتیجه‌ی سرچ،
   یه کلیک دوم هم رو اسم مخاطب که بالای چت (هدر) ظاهر می‌شه انجام می‌شه - طبق
   codegen واقعی تست‌شده توسط کاربر. این کلیک دوم هم تأیید می‌کنه چت واقعاً
   به مخاطب درست سوییچ شده، هم اگه سوییچ نشده باشه، به‌جای ادامه‌ی ریسکی
   (که ممکنه پیام به چت اشتباه بره)، با خطای واضح متوقف می‌شه.
"""

import asyncio
import hashlib
import json
import os
import re
import time
from datetime import datetime

import jdatetime
from playwright.async_api import async_playwright

from dotenv import load_dotenv

from core import runlog

# Credentials come from Senders/.env (gitignored) - the same PEZHVA_USERNAME/
# PEZHVA_PASSWORD that send_message_v2.py reads (same messenger account).
# Deliberately NOT raised at import time: payamresan.py imports this module
# unconditionally, so a missing .env must not break v2 - login() fails
# loudly instead, only if v1 is actually used.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
USERNAME = os.environ.get("PEZHVA_USERNAME")
PASSWORD = os.environ.get("PEZHVA_PASSWORD")

# اگه صحیح باشه، مرورگر بدون رندر واقعی UI اجرا میشه (سریع‌تر). برای دیباگ
# کردن مشکلات، موقتاً False بذارش تا مرورگر رو واقعی ببینی.
HEADLESS = False

SEARCH_RESULT_WAIT_MS = 500  # صبر بعد از تایپ تو باکس سرچ

# بعد از کلیک روی نتیجه‌ی سرچ، چقدر فرصت بدیم تا هدر چت (.chatContactName)
# واقعاً به مخاطب جدید سوییچ کنه، قبل از اینکه mismatch رو قطعی حساب کنیم -
# ببین open_chat برای دلیل دقیق race
HEADER_SWITCH_TIMEOUT_SECONDS = 6

# فاصله‌ی هر تلاش poll تو _verify_sent_message_content - چون بلافاصله بعد
# مطابقت برمی‌گردیم (نه صبر تا آخر timeout_ms)، این عدد کوچیک نگه‌داشته شده
# تا تو حالت عادی (بدون race) هیچ تأخیر محسوسی اضافه نشه
CONTENT_VERIFY_POLL_MS = 200

# فاصله‌ی زمانی بین ارسال یک مخاطب و رفتن سراغ مخاطب بعدی (تو هر تب) - هم به
# سایت فشار کمتری میاره، هم اگه سایت کند بشه UI فرصت stabilize شدن داره
INTERVAL_SECONDS = 1

# پیش‌فرض timeout هر اکشن (کلیک/wait_for/...) - رو روز شلوغ اگه بازم timeout
# دیدی، همین عدد رو (به میلی‌ثانیه) بیشتر کن، نیازی به تغییر جای دیگه نیست
DEFAULT_ACTION_TIMEOUT_MS = 30000

# تعداد تب‌های هم‌زمان پیش‌فرض (نه Thread واقعی - concurrency با asyncio)
DEFAULT_NUM_TABS = 2

# اسمی که بعد از لاگین موفق و لود کامل صفحه، جایی تو صفحه (مثلاً نام اکانت)
# نمایش داده میشه. با ظاهر شدنش مطمئن میشیم صفحه واقعاً آماده‌ست.
ACCOUNT_DISPLAY_NAME = "گزارشات"

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# نگاشت حروف عربی به معادل فارسی‌شون + کاراکترهای نامرئی رایج (نیم‌فاصله،
# نشانگرهای RTL/LTR) - چون بعضی اسامی با کیبورد عربی، بعضی با فارسی تایپ شدن
_ARABIC_TO_PERSIAN_MAP = str.maketrans({
    "ي": "ی",   # یِ عربی
    "ك": "ک",   # کافِ عربی
    "ة": "ه",   # تاء مربوطه
    "أ": "ا",
    "إ": "ا",
    "ؤ": "و",
    "ئ": "ی",
    "\u200c": " ",  # نیم‌فاصله -> فاصله‌ی معمولی
    "\u200f": "",   # نشانگر RTL نامرئی -> حذف
    "\u200e": "",   # نشانگر LTR نامرئی -> حذف
})


def _normalize_whitespace(text: str) -> str:
    """چند فاصله‌ی پشت‌سرهم رو یکی می‌کنه + trim - برای مقایسه‌ی متن‌ها"""
    return re.sub(r"\s+", " ", text).strip()


def _strip_english_suffix(name: str) -> str:
    """پسوند انگلیسی انتهای اسم (مثل VP/RW/DJ) رو حذف می‌کنه"""
    return re.sub(r"\s*[A-Za-z]+\s*$", "", name)


def _normalize_name_fully(name: str) -> str:
    """
    نرمال‌سازی جامع اسم برای مقایسه/سرچ fallback - همه‌ی حالت‌های شناخته‌شده
    رو یکجا پوشش می‌ده:
        - حروف عربی -> معادل فارسی (ي->ی، ك->ک، ...)
        - نیم‌فاصله/کاراکترهای نامرئی -> فاصله‌ی معمولی یا حذف
        - فاصله‌های چندتایی/پشت‌سرهم -> یک فاصله
        - پسوند انگلیسی انتهای اسم -> حذف
        - trim ابتدا/انتها

    ⚠️ ریسک پذیرفته‌شده: اگه دو نفر دقیقاً هم‌اسم فارسی (فقط پسوند فرق) باشن،
    ممکنه با هم اشتباه گرفته بشن - این ریسک عمداً و آگاهانه قبول شده.
    """
    text = name.translate(_ARABIC_TO_PERSIAN_MAP)
    text = _strip_english_suffix(text)
    text = _normalize_whitespace(text)
    return text


def _normalize_whitespace(text: str) -> str:
    """چند فاصله‌ی پشت‌سرهم رو یکی می‌کنه + trim - برای مقایسه‌ی متن‌ها"""
    return re.sub(r"\s+", " ", text).strip()


def _strip_english_suffix(name: str) -> str:
    """
    پسوند انگلیسی انتهای اسم (مثل VP/RW/DJ/NH/VH/DGH/NP) رو حذف می‌کنه و
    فاصله‌های اضافه رو یکی می‌کنه - چون سرچ/تطبیق روی خودِ اسم فارسی خیلی
    مطمئن‌تره تا وابسته‌کردن به دقیق‌بودن پسوند/فاصله‌های اطرافش.

    ⚠️ ریسک پذیرفته‌شده: اگه دو نفر دقیقاً هم‌اسم فارسی (فقط پسوند فرق) باشن،
    ممکنه با هم اشتباه گرفته بشن - این ریسک فعلاً عمداً قبول شده.
    """
    stripped = re.sub(r"\s*[A-Za-z]+\s*$", "", name)
    return _normalize_whitespace(stripped)


def _compute_run_id(recipients: list) -> str:
    """
    یه fingerprint کوتاه از محتوای این batch می‌سازه (بر اساس contact+caption
    همه‌ی مخاطبین، مرتب‌شده). اگه دقیقاً همین batch (همون سیکل، همون کپشن‌ها)
    دوباره اجرا بشه، همین fingerprint دوباره ساخته می‌شه - پس resume درست کار
    می‌کنه. اگه سیکل بعدی با کپشن‌های جدید باشه، fingerprint فرق می‌کنه و از
    صفر شروع می‌شه (که درسته، چون اون یه batch جدیدیه).
    """
    fingerprint_lines = sorted(
        f"{r['contact']}|{r.get('caption', '')}" for r in recipients
    )
    fingerprint = "\n".join(fingerprint_lines)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12]


def _resume_key(contact_name: str, raw_caption) -> str:
    """
    کلید یکتای هر *پیام* برای فایل resume - مخاطب+کپشن خام، نه فقط اسم
    مخاطب. چرا: یه مقصد مشترک (مثلاً یه کانال) ممکنه تو یه سیکل چندتا پیام
    با کپشن‌های متفاوت بگیره (چندتا گزارش که به یه کانال میرن). اگه کلید
    فقط اسم مخاطب بود، بعد از crash وسط batch، موفقیت پیام اول همون مخاطب
    باعث می‌شد resume اشتباهاً بقیه‌ی پیام‌های *متفاوت* همون مخاطب رو هم
    «قبلاً انجام‌شده» حساب کنه و برای همیشه رد کنه.
    """
    return f"{contact_name}\x1f{raw_caption or ''}"


def build_dynamic_text() -> str:
    """فقط fallback - اگه caption به هر دلیلی خالی/None باشه"""
    now = jdatetime.datetime.now()
    time_str = now.strftime("%H:%M:%S").translate(PERSIAN_DIGITS)
    day_str = str(now.day).translate(PERSIAN_DIGITS)
    month_name = now.j_months_fa[now.month - 1]
    return f"سلام\nامروز {day_str} {month_name} ساعت {time_str} ثانیه است"


async def close_notification_popup(page):
    x_icon = page.locator(".alertIcon.hand > svg")
    try:
        await x_icon.wait_for(state="visible", timeout=5000)
        await x_icon.click()
        return
    except Exception:
        pass

    close_btn = page.get_by_role("button", name="بستن", exact=True)
    try:
        await close_btn.wait_for(state="visible", timeout=3000)
        await close_btn.click()
    except Exception:
        pass


async def login(page):
    if not USERNAME or not PASSWORD:
        raise RuntimeError("PEZHVA_USERNAME / PEZHVA_PASSWORD not set in Senders/.env (see .env.example)")
    await page.locator('input[type="text"]').click()
    await page.locator('input[type="text"]').fill(USERNAME)
    await page.locator('input[type="password"]').click()
    await page.locator('input[type="password"]').fill(PASSWORD)
    await page.locator('input[type="password"]').press("Enter")
    await page.wait_for_load_state("networkidle")

    await close_notification_popup(page)
    await wait_for_page_ready(page)


async def wait_for_page_ready(page):
    """
    منتظر می‌مونه تا اسم اکانت واقعاً تو صفحه ظاهر بشه؛ یعنی صفحه کامل لود
    شده و آماده‌ی سرچ مخاطبینه. هم بعد از لاگین، هم بعد از باز کردن تب جدید
    (که از قبل لاگین‌شده) استفاده میشه.
    """
    await page.get_by_text(ACCOUNT_DISPLAY_NAME, exact=True).wait_for(
        state="visible", timeout=20000
    )


async def open_chat(page, contact_name: str):
    """
    چت مخاطب رو باز می‌کنه و *تأیید* می‌کنه که واقعاً چت درست بازه.

    ⚠️ محافظ حیاتی امنیتی: فقط کلیک روی نتیجه‌ی سرچ کافی نیست - چون ممکنه
    چت هنوز کامل سوییچ نشده باشه (تایمینگ) یا نتیجه‌ی اشتباهی کلیک شده باشه.
    برای همین، بعد از باز شدن چت، محتوای هدر چت (.chatContactName) رو
    می‌خونیم (بدون کلیک روش) و با contact_name (نرمال‌شده) مقایسه می‌کنیم.
    اگه مطابقت نداشت، یعنی چت درست باز نشده و RuntimeError می‌دیم (به‌جای
    ریسک ارسال به مخاطب اشتباه).

    ⚠️ Fallback سرچ: اگه سرچ اولیه (با اسم دقیقاً همون‌طور که تو دیتاست) هیچی
    پیدا نکرد، یه بار دیگه با نسخه‌ی *کاملاً نرمال‌شده* (عربی->فارسی، فاصله‌های
    اضافه، بدون پسوند انگلیسی) امتحان می‌کنیم - چون اسامی از منابع مختلف
    (کیبورد عربی/فارسی، فاصله‌ی نامنظم) میان و ممکنه دقیقاً با چیزی که تو
    سایت ثبت شده یکی نباشه.
    """
    search_box = page.get_by_role("textbox", name="جست‌وجو در مخاطبان")
    await search_box.click(force=True)
    await search_box.fill("")
    await search_box.fill(contact_name)
    await page.wait_for_timeout(SEARCH_RESULT_WAIT_MS)

    result = page.get_by_text(re.compile(re.escape(contact_name)))
    if await result.count() == 0:
        normalized = _normalize_name_fully(contact_name)
        await search_box.fill("")
        await search_box.fill(normalized)
        await page.wait_for_timeout(SEARCH_RESULT_WAIT_MS)
        result = page.get_by_text(re.compile(re.escape(normalized)))
        if await result.count() == 0:
            raise RuntimeError(
                f"نتیجه‌ای برای سرچ «{contact_name}» پیدا نشد "
                f"(حتی بعد از نرمال‌سازی به «{normalized}»)"
            )

    await result.first.click(force=True, timeout=10000)

    # ─── تأیید سوییچ چت - poll، نه یه چک لحظه‌ای ─────────────────────────────
    # سلکتور دقیق از Inspect واقعی: <span class="chatContactName ..."> بالای
    # چت. عمداً روش کلیک نمی‌کنیم (فقط inner_text می‌گیریم) چون کلیک ممکنه
    # یه پنل جانبی (پروفایل مخاطب) باز کنه که با مراحل بعدی تداخل کنه.
    #
    # ⚠️ چرا poll نه یه‌بار چک: اگه یه چت قبلی همین الان باز بوده، این عنصر از
    # قبل visible هست - پس wait_for(state="visible") فوراً برمی‌گرده بدون اینکه
    # واقعاً صبر کنه محتواش به مخاطب جدید سوییچ کنه (کلیک روی نتیجه‌ی سرچ،
    # عوض‌شدن هدر رو async/client-side انجام می‌ده). تو تست زنده‌ی واقعی این
    # race دقیقاً همین باعث شد: هدر هنوز اسم چت قبلی رو نشون می‌داد، کد بلافاصله
    # چک می‌کرد و مخاطب رو اشتباهاً "mismatch" رد می‌کرد - در حالی که چند صدم
    # ثانیه بعد خودش درست می‌شد. راه‌حل: به‌جای یه‌بار خوندن، تا
    # HEADER_SWITCH_TIMEOUT_SECONDS مطابقت رو poll می‌کنیم و فقط اگه واقعاً تا
    # آخر این بازه هم مطابقت پیدا نشد، mismatch رو قطعی حساب می‌کنیم - محافظ
    # امنیتی دست‌نخورده می‌مونه، فقط فرصت واقعی برای سوییچ شدن هم داده می‌شه.
    header_name = page.locator(".chatContactName")
    target_normalized = _normalize_name_fully(contact_name)
    header_text = ""
    deadline = time.monotonic() + HEADER_SWITCH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            await header_name.wait_for(state="visible", timeout=1000)
            header_text = await header_name.inner_text()
        except Exception:
            header_text = ""
        if target_normalized in _normalize_name_fully(header_text):
            return
        await page.wait_for_timeout(150)

    raise RuntimeError(
        f"چت باز‌شده با «{contact_name}» مطابقت نداشت (هدر نشون داد: «{header_text}») - "
        f"برای جلوگیری از ارسال به چت اشتباه، این مخاطب رد شد"
    )


async def _wait_for_new_message_sent(page, timeout_ms: int = 30000):
    """
    ⚠️ محافظ حیاتی امنیتی (لایه‌ی جدید): برخلاف نسخه‌ی قبلی که با
    page.locator('[title="ارسال شد"], [title="دیده شد"]').last رو *کل صفحه*
    دنبال تیک می‌گشت، این نسخه فقط داخل ردیف پیامِ *تازه‌ارسال‌شده* (اولین
    فرزند مستقیم .scroll-list.inner - طبق همون قرارداد _verify_sent_message_content)
    دنبال تیک می‌گرده.

    چرا این تغییر لازم بود: تست زنده نشون داد وقتی چتی از قبل یه پیام قدیمی‌تر
    با تیک "ارسال شد" داشت، و پیام تازه (به‌خصوص پیوست عکس/فایل که چون آپلودش
    زمان می‌بره یه حالت میانی/لودینگ داره) هنوز واقعاً تحویل نشده بود، .last
    همون تیک قدیمی رو پیدا می‌کرد و کد اشتباهاً فکر می‌کرد ارسال تازه تموم
    شده - و بلافاصله می‌رفت سراغ پاک‌کردن مکالمه، درحالی‌که آپلود هنوز در
    حال انجام بود. اسکرین‌شات گرفته‌شده بلافاصله بعد از "تأیید" این نسخه‌ی
    قبلی، وضعیت اسپینر/لودینگ رو نشون می‌داد، نه تیک واقعی.

    قبل از چک تیک، اگه لودر آپلود (.download-loader) تو همین ردیف وجود داشته
    باشه (فقط پیام‌های عکس/فایل، نه متن خالص)، اول صبر می‌کنیم محو بشه.
    """
    newest_row = page.locator(".scroll-list.inner > div").first

    loader = newest_row.locator(".download-loader")
    try:
        if await loader.count() > 0:
            await loader.first.wait_for(state="hidden", timeout=timeout_ms)
    except Exception:
        pass  # لودر هیچ‌وقت ظاهر نشد یا از قبل محو بود - مشکلی نیست، می‌ریم سراغ چک تیک

    tick = newest_row.locator('[title="ارسال شد"], [title="دیده شد"]')
    await tick.first.wait_for(state="visible", timeout=timeout_ms)


async def _verify_header_still_correct(page, contact_name: str):
    """
    ⚠️ محافظ حیاتی امنیتی (لایه‌ی دوم): درست بعد از دیدن تیک «ارسال شد/دیده
    شد»، دوباره چک می‌کنیم هدر چت هنوز همون مخاطبیه که ارسال قبلش تأیید شده
    بود. اگه نه، یعنی بین لحظه‌ی تأیید اولیه و لحظه‌ی واقعی ارسال، یه‌جوری
    چت عوض شده - این خودش یعنی این ارسال باید مشکوک/ناموفق حساب بشه.
    بدون کلیک، فقط خوندن محتوای .chatContactName.
    """
    header_name = page.locator(".chatContactName")
    try:
        await header_name.wait_for(state="visible", timeout=8000)
        header_text = await header_name.inner_text()
    except Exception:
        raise RuntimeError(
            f"بعد از ارسال، هدر چت پیدا نشد - این ارسال مشکوکه، به‌عنوان ناموفق ثبت شد"
        )

    if _normalize_name_fully(contact_name) not in _normalize_name_fully(header_text):
        raise RuntimeError(
            f"بعد از ارسال، هدر چت «{header_text}» بود نه «{contact_name}» - این ارسال "
            f"مشکوکه (احتمال رفتن پیام به چت اشتباه)، به‌عنوان ناموفق ثبت شد"
        )


async def _verify_sent_message_content(page, caption: str, timeout_ms: int = 10000):
    """
    ⚠️ محافظ حیاتی امنیتی (لایه‌ی سوم، قوی‌ترین): تو این چت، پیام‌های جدید
    *بالای* لیست پیام‌ها میان (اولین فرزند مستقیم .scroll-list.inner)، نه
    پایین. یعنی همیشه اولین ردیف = آخرین پیامی که تو همین چت رد و بدل شده.
    متن واقعی همون ردیف رو با کپشنی که خودمون قصد ارسالش رو داشتیم مقایسه
    می‌کنیم - این مستقل از هدر چته، مستقیم خودِ محتوای واقعی پیام رو چک می‌کنه.

    ⚠️ .inner_text() تمام متن‌های تو در توی همه‌ی فرزندهای داخل اون ردیف رو
    recursive جمع می‌کنه - پس چه پیام فقط‌متن باشه چه عکس+کپشن (که کپشنش
    داخل .image-caption > p تو در توی همون ردیف قرار داره)، این تابع بدون
    تغییر هر دو حالت رو پوشش می‌ده.

    ⚠️ چرا poll نه یه‌بار چک (تست زنده نشون داد، مخصوصاً وقتی چندتا پیام
    پشت‌سرهم به یه چت *بدون clear* می‌رن): تیک «ارسال شد» گاهی زودتر از
    خودِ رندر/insert شدنِ ردیف پیامِ تازه تو DOM ظاهر می‌شه - یعنی وقتی این
    تابع صدا زده می‌شه، ردیف اول لیست هنوز پیام *قبلی* رو نشون می‌ده، نه
    پیام تازه. به‌جای یه‌بار خوندن و رد کردن، تا timeout_ms مطابقت رو poll
    می‌کنیم و **به محض مطابقت فوراً برمی‌گردیم** (نه صبر تا آخر بازه) - پس تو
    حالت عادی (که معمولاً فوراً مطابقت داره) هیچ تأخیر اضافه‌ای ایجاد نمی‌شه؛
    فقط تو همون لحظه‌ی نادر race، فرصت واقعی برای رندر شدن هم داده می‌شه.
    محافظ امنیتی دست‌نخورده می‌مونه: اگه تا آخر بازه هم مطابقت پیدا نشد،
    mismatch قطعی حساب می‌شه (به‌جای false-negative سریع).

    timeout_ms: سقف زمانی poll. پیام‌های عکس‌دار (که آپلود/رندرشون کندتره)
    به timeout بیشتری نیاز دارن؛ برای پیام‌های فقط‌متن پیش‌فرض کافیه.

    فقط خط اول کپشن («سلام {نام} عزیز») رو به‌عنوان امضای منحصربه‌فرد چک
    می‌کنیم (نه کل متن) چون ** (بولد مارک‌داون) و _ (آندرلاین/ایتالیک
    مارک‌داون) ممکنه تو نمایش واقعی رندر نشن و باعث false-negative بشن -
    تست زنده‌ی 2026-09-15 دقیقاً همین رو با یه کپشن حاوی "_" نشون داد: پیام
    واقعاً رفته بود ولی چون caption_signature هنوز "_" داشت و پلتفرم موقع
    نمایش حذفش کرده بود، مطابقت رد شد (send_status اشتباهاً "ناموفق" ثبت
    شد، که هم clear رو غیرفعال کرد هم باعث ارسال تکراری تو retry pass شد).
    """
    first_row = page.locator(".scroll-list.inner > div").first
    caption_signature = caption.strip().split("\n")[0].replace("*", "").replace("_", "").strip()
    caption_signature = _normalize_whitespace(caption_signature.translate(_ARABIC_TO_PERSIAN_MAP))

    message_text = ""
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        try:
            await first_row.wait_for(state="visible", timeout=1000)
            message_text = await first_row.inner_text()
        except Exception:
            message_text = ""

        message_text_normalized = message_text.replace("_", "")
        message_text_normalized = _normalize_whitespace(message_text_normalized.translate(_ARABIC_TO_PERSIAN_MAP))
        if caption_signature in message_text_normalized:
            return

        await page.wait_for_timeout(CONTENT_VERIFY_POLL_MS)

    raise RuntimeError(
        f"متن پیام ارسالی با کپشن مطابقت نداشت - انتظار داشتیم شامل "
        f"«{caption_signature}» باشه، ولی متن واقعی این بود: «{message_text[:120]}»"
    )


async def attach_and_send_image(page, image_path: str, caption: str, contact_name: str = None):
    await page.locator(".uploader-dropdown-icon").click(force=True)
    await page.locator('input[type="file"]').set_input_files(image_path)

    caption_box = page.get_by_role("textbox", name="توضیحات")
    await caption_box.wait_for(state="visible", timeout=8000)
    await caption_box.click(force=True)
    await caption_box.fill(caption)

    confirm_btn = page.get_by_text("تایید", exact=True)
    await confirm_btn.click(force=True)

    await _wait_for_new_message_sent(page)

    if contact_name:
        await _verify_header_still_correct(page, contact_name)
    await _verify_sent_message_content(page, caption, timeout_ms=15000)


async def send_text_only(page, caption: str, contact_name: str = None):
    """
    وقتی مخاطب عکس اختصاصی نداره (image=None)، به‌جای آپلود عکس فقط متن رو
    تو باکس اصلی پیام می‌فرستیم. selector دقیق از codegen واقعی گرفته شده
    (نه حدس): باکس با name="پیام شما"، دکمه‌ی ارسال #btnSend.
    """
    message_box = page.get_by_role("textbox", name="پیام شما")

    try:
        await message_box.wait_for(state="visible", timeout=5000)
    except Exception:
        # fallback: اگه به هر دلیلی این selector دقیق کار نکرد (مثلاً UI عوض
        # شده)، چند حالت رایج دیگه رو هم امتحان می‌کنیم قبل از شکست کامل
        found = False
        for name in ["پیام", "پیام خود را بنویسید", "نوشتن پیام"]:
            candidate = page.get_by_role("textbox", name=name)
            try:
                await candidate.wait_for(state="visible", timeout=1500)
                message_box = candidate
                found = True
                break
            except Exception:
                continue

        if not found:
            candidate = page.locator('[contenteditable="true"], textarea').last
            try:
                await candidate.wait_for(state="visible", timeout=3000)
                message_box = candidate
            except Exception:
                raise RuntimeError(
                    "باکس نوشتن پیام پیدا نشد؛ selector رو دستی مشخص کن "
                    "(با Inspect کردن باکس پیام توی مرورگر)."
                )

    await message_box.click(force=True)
    await message_box.fill(caption)

    send_btn = page.locator("#btnSend")
    await send_btn.click(force=True)

    await _wait_for_new_message_sent(page)

    if contact_name:
        await _verify_header_still_correct(page, contact_name)
    await _verify_sent_message_content(page, caption)


def has_valid_image(image_path) -> bool:
    return bool(image_path) and os.path.isfile(image_path)


async def clear_current_chat_history(page):
    """
    مکالمهٔ چتی که همین الان بازه رو پاک می‌کنه (تا اکانت سنگین نشه و دفعه‌های
    بعد کند لود نشه): آواتار داخل چت -> «پاک‌کردن مکالمات» -> تایید «بله»

    ⚠️ selector آواتار (2026-09-15): تست زنده نشون داد کلاس‌های سایت از
    ".avatar-frame"/".avatar" به ".ui-avatar-frame"/".ui-avatar" عوض شدن
    (".contactAvatar" بیرونی تغییر نکرده) - قبلش این باعث می‌شد
    clear_current_chat_history همیشه با timeout رو خودِ پیدا کردن آواتار
    fail بشه (پیام درست می‌رفت، فقط پاک‌کردن انجام نمی‌شد).

    ⚠️ ترکیبی از selectorهای دقیق‌تر (از codegen واقعی) + صبرهای کوتاه + retry:
    ۱. بعد از کلیک «پاک‌کردن مکالمات»، چک می‌کنیم متن هشدار واقعاً ظاهر شده
       (یعنی پاپ‌آپ واقعاً باز شده، نه اینکه قبلاً بسته بوده یا اصلاً باز نشده).
    ۲. رو خودِ باکس مودال (نه فقط دکمه) کلیک می‌کنیم - این دقیقاً رفتاریه که
       تو ضبط دستی (codegen) پایدار بود و احتمالاً focus/hover درست جا میندازه.
    ۳. کلیک «بله» رو تا ۳ بار retry می‌کنیم و هر بار چک می‌کنیم مودال واقعاً
       بسته شده (hidden) یا نه.
    """
    avatar = page.locator(".contactAvatar > .ui-avatar-frame > .ui-avatar")
    await avatar.wait_for(state="visible", timeout=10000)
    await avatar.click(force=True)

    clear_btn = page.get_by_text("پاک‌کردن مکالمات")
    await clear_btn.wait_for(state="visible", timeout=10000)
    await clear_btn.click(force=True)

    # صبر تا مودال تایید کامل رندر/animate بشه
    await page.wait_for_timeout(500)

    # چک می‌کنیم پاپ‌آپ واقعاً باز شده - اگه ظرف ۵ ثانیه ظاهر نشد یعنی یه‌جوری
    # اصلاً باز نشده (نه فقط دیر باز شده)
    warning_text = page.get_by_text("از پاک کردن مکالمات این مخاطب اطمینان دارید؟")
    await warning_text.wait_for(state="visible", timeout=5000)

    # کلیک رو خودِ باکس مودال (شامل کل متن هشدار + دکمه‌های بله/بستن) - این
    # مرحله رو codegen واقعی ضبط کرده بود و باعث پایدارتر شدن کلیک بعدی می‌شه
    modal_box = page.locator("div").filter(
        has_text="هشداراز پاک کردن مکالمات این مخاطب اطمینان دارید؟بلهبستن"
    ).nth(2)
    await modal_box.wait_for(state="visible", timeout=5000)
    await modal_box.click(force=True)

    await page.wait_for_timeout(300)

    confirm_btn = page.get_by_text("بله")
    await confirm_btn.wait_for(state="visible", timeout=10000)

    for attempt in range(1, 4):
        await confirm_btn.click(force=True)
        try:
            # اگه مودال واقعاً بسته شده باشه، این دکمه دیگه visible نیست
            await confirm_btn.wait_for(state="hidden", timeout=2000)
            return
        except Exception:
            if attempt < 3:
                await page.wait_for_timeout(500)  # یه کم بیشتر صبر و دوباره تلاش
                continue

    raise RuntimeError("دکمه‌ی «بله» بعد از ۳ بار تلاش هنوز مودال رو نبست")


async def _recover_page_after_failure(page):
    """
    ⚠️ محافظ حیاتی: وقتی ارسال یه نفر fail می‌شه (مثلاً تیک «ارسال شد»
    تایم‌اوت می‌خوره)، ممکنه صفحه وسط یه وضعیت نیمه‌کاره (آپلود در حال انجام،
    مودال باز، سرچ نیمه‌تایپ) گیر کرده باشه. بدون ریکاوری، این وضعیت برای
    نفر بعدی می‌مونه و باعث fail زنجیره‌ای می‌شه (دقیقاً همون چیزی که تو لاگ
    واقعی دیده شد: یکی fail شد، همه‌ی بعدی‌ها هم fail شدن).
    برای همین بعد از هر شکست ارسال، صفحه رو reload می‌کنیم تا نفر بعدی از
    یه وضعیت کاملاً تازه شروع کنه.
    """
    try:
        await page.reload(wait_until="load", timeout=DEFAULT_ACTION_TIMEOUT_MS)
        await wait_for_page_ready(page)
    except Exception:
        pass   # اگه ریکاوری هم شکست خورد، همون‌طوری ادامه می‌دیم؛ بهتر از توقف کامله


async def process_contact_group(page, contact_name: str, messages: list, clear_after_send: bool = True) -> list:
    """
    یک مقصد (contact) رو فقط *یک‌بار* open_chat می‌کنه، بعد همه‌ی پیام‌های
    این سیکل که مقصدشون همینه (مثلاً چندتا خروجی گزارش که به یه کانال
    مشترک میرن) رو پشت‌سرهم، بدون سرچ/باز کردن دوباره، ارسال می‌کنه.

    messages: [{"image": مسیر یا None, "caption": متن یا None}, ...]
    خروجی: لیستی از دیکشنری‌نتیجه (فرمت مثل نسخه‌ی قبلی تک‌پیامی)، یکی به
    ازای هر پیام - fail شدن یکی، بقیه‌ی پیام‌های همین مقصد رو متوقف نمی‌کنه
    (فقط اگه صفحه ریلود بشه، قبل پیام بعدی چت دوباره باز می‌شه).

    ⚠️ چرا گروه‌بندی لازم بود: قبلاً هر پیام (حتی برای همون مقصد) open_chat
    مستقل خودش رو داشت. اگه دو پیام برای یه مقصد مشترک تو دو تب/چانک ایزوله
    جدا می‌افتاد، هر دو هم‌زمان همون چت واقعی رو باز می‌کردن - چون چت روی
    سرور مشترکه، پیام تب دیگه هم تو لیست پیام‌های این تب دیده می‌شد و
    verify_sent_message_content محتوای پیام تب دیگه رو به‌جای پیام خودش
    می‌خوند (mismatch واقعی، تو تست زنده دیده شد). گروه‌بندی بر اساس مقصد -
    با تضمین اینکه هر مقصد همیشه توسط دقیقاً یک تب پردازش بشه (ببین
    _group_by_contact) - این race رو از ریشه حذف می‌کنه.

    ⚠️ clear_after_send: این فایل بین چند پروژه‌ی مختلف مشترکه/مرجعه. تو
    پروژه‌های ارسال انبوه (تعداد بالا)، پاک‌نکردن مکالمه باعث سنگین و
    غیرقابل‌استفاده شدن اکانت می‌شه - پس اونجا باید روشن بمونه (پیش‌فرض True).
    تو پروژه‌هایی مثل Robot_Analytics فراخوان باید صریحاً False پاس بده.
    پاک‌کردن (اگه روشن باشه) فقط *یک‌بار* در آخر گروه انجام می‌شه، نه به ازای
    هر پیام - چون چت همچنان بازه، نیازی به پاک‌کردن میانی نیست.
    """
    results = []
    chat_open = False
    any_success = False

    for m in messages:
        image_path = m.get("image")
        raw_caption = m.get("caption")
        caption = raw_caption or build_dynamic_text()
        start_time = datetime.now()
        send_status = "موفق"
        send_error = ""

        if not chat_open:
            try:
                await open_chat(page, contact_name)
                chat_open = True
            except Exception as e:
                send_status = "ناموفق"
                send_error = f"باز کردن چت شکست خورد: {e}"

        if send_status == "موفق":
            try:
                if has_valid_image(image_path):
                    await attach_and_send_image(page, image_path, caption, contact_name)
                else:
                    await send_text_only(page, caption, contact_name)
            except Exception as e:
                send_status = "ناموفق"
                send_error = str(e)
                await _recover_page_after_failure(page)
                chat_open = False  # صفحه ریلود شد - قبل پیام بعدی همین مقصد باید دوباره باز بشه

        end_time = datetime.now()
        duration = round((end_time - start_time).total_seconds(), 2)
        results.append({
            "contact_name": contact_name,
            "image_path": image_path,
            "caption": caption,
            "raw_caption": raw_caption,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "send_status": send_status,
            "send_error": send_error,
            "clear_status": "",
            "clear_error": "",
        })
        if send_status == "موفق":
            any_success = True

        await asyncio.sleep(INTERVAL_SECONDS)

    if clear_after_send:
        if chat_open and any_success:
            try:
                await clear_current_chat_history(page)
                clear_status, clear_error = "موفق", ""
            except Exception as e:
                clear_status, clear_error = "ناموفق", str(e)
            for r in reversed(results):
                if r["send_status"] == "موفق":
                    r["clear_status"], r["clear_error"] = clear_status, clear_error
                    break
        for r in results:
            if not r["clear_status"]:
                r["clear_status"] = "انجام نشد (ارسال ناموفق بود)"
    else:
        for r in results:
            r["clear_status"] = "غیرفعال (پاک‌کردن برای این پروژه خاموشه)"

    return results


def format_result_line(idx: int, total: int, result: dict) -> str:
    send_ok = result["send_status"] == "موفق"
    clear_ok = result["clear_status"] == "موفق"
    status_word = "OK" if send_ok else "FAILED"
    clear_word = "cleared" if clear_ok else ("clear-failed" if send_ok else "not-cleared")
    timestamp = result["start_time"].strftime("%H:%M:%S")
    line = (
        f"[{idx}/{total}] {timestamp} {result['contact_name']} - "
        f"{status_word} ({clear_word}) - {result['duration']:.2f}s"
    )
    if not send_ok:
        line += f" - {result['send_error']}"
    return line


_NOT_ATTEMPTED_CLEAR_STATUSES = ("انجام نشد (ارسال ناموفق بود)", "غیرفعال (پاک‌کردن برای این پروژه خاموشه)")


def _normalize_result(result: dict) -> dict:
    """Maps this file's own Persian-status result dict to the version-
    agnostic item shape core/runlog.py (and everything downstream of it,
    including v2) understands - see core/runlog.py's docstring. Called
    right before on_result(), never stored anywhere itself.

    known_contact is always None here: v1 has no id/cache concept, it
    always searches by name fresh - "not applicable", not "unknown"."""
    return {
        "ok": result["send_status"] == "موفق",
        "contact": result["contact_name"],
        "resume_key": _resume_key(result["contact_name"], result["raw_caption"]),
        "error": result["send_error"] or None,
        "duration_sec": result["duration"],
        "known_contact": None,
        "cleared": {
            "attempted": result["clear_status"] not in _NOT_ATTEMPTED_CLEAR_STATUSES,
            "ok": result["clear_status"] == "موفق",
            "error": result["clear_error"] or None,
        },
    }


def _split_into_chunks(items: list, num_chunks: int) -> list:
    num_chunks = max(1, min(num_chunks, len(items))) if items else 1
    chunks = [[] for _ in range(num_chunks)]
    for i, item in enumerate(items):
        chunks[i % num_chunks].append(item)
    return [c for c in chunks if c]


def _group_by_contact(recipients: list) -> list:
    """
    مخاطبین رو بر اساس مقصد (contact) گروه می‌کنه، با حفظ ترتیب اول ظهور -
    هر عنصر خروجی: {"contact": نام, "messages": [{"image","caption"}, ...]}.

    ⚠️ چرا این لازمه: چون تقسیم قبلی (round-robin روی لیست تخت پیام‌ها) ممکن
    بود پیام‌های یه مقصد مشترک (مثلاً چندتا خروجی گزارش که به یه کانال
    میرن) بین چند تب/BrowserContext ایزوله جدا پخش کنه. چون چت روی سرور
    مشترکه، اگه دو تب هم‌زمان همون مقصد رو باز کنن، پیام یه تب تو لیست
    پیام‌های تب دیگه هم دیده می‌شه و verify_sent_message_content اشتباهاً
    محتوای پیام تب دیگه رو می‌خونه (mismatch). گروه‌بندی تضمین می‌کنه هر
    مقصد دقیقاً توسط یک تب، یک‌بار open_chat بشه.
    """
    order = []
    grouped = {}
    for r in recipients:
        contact = r["contact"]
        if contact not in grouped:
            grouped[contact] = []
            order.append(contact)
        grouped[contact].append({"image": r.get("image"), "caption": r.get("caption")})
    return [{"contact": c, "messages": grouped[c]} for c in order]


def _results_to_recipients(results: list) -> list:
    """نتایج (فرمت process_contact_group) رو به فرمت ورودی recipient برمی‌گردونه"""
    return [{"contact": r["contact_name"], "image": r["image_path"], "caption": r["raw_caption"]} for r in results]


async def _retry_pass(browser, run_results: list, on_result,
                      num_tabs: int = DEFAULT_NUM_TABS, clear_after_send: bool = True):
    """
    بعد از تموم شدن کل batch صدا زده می‌شه (نتایج از حافظه‌ی همین اجرا، نه از
    خوندن دوباره‌ی فایل لاگ - چون همینجا در حافظه داریمشون، مطمئن‌تر و بدون
    نیاز به فیلتر بازه‌ی زمانیه):

    - هرکی send_status ش "ناموفق" بود -> از صفر (سرچ+ارسال+پاک‌کردن) دوباره.
    - هرکی send_status ش "موفق" ولی clear_status ش دقیقاً "ناموفق" بود (نه
      "غیرفعال" - یعنی واقعاً تلاش شده و شکست خورده، نه اینکه از اول خاموش
      بوده) -> فقط مرحله‌ی پاک‌کردن (بدون ارسال دوباره‌ی پیام، چون پیام از
      قبل رفته).

    ⚠️ الان دقیقاً مثل batch اصلی موازی اجرا می‌شه: لیست‌ها بین num_tabs
    context کاملاً ایزوله (لاگین مستقل هرکدوم) تقسیم می‌شه - نه یک context
    و پشت‌سرهم. هم سریع‌تره، هم چون هر تب ایزوله‌ست، اگه یکی گیر کنه
    (وضعیت نیمه‌کاره)، بقیه‌ی تب‌ها ازش بی‌خبرن و fail زنجیره‌ای نمی‌شه.
    """
    to_resend = [r for r in run_results if r["send_status"] != "موفق"]
    to_clear_only = [r for r in run_results if r["send_status"] == "موفق" and r["clear_status"] == "ناموفق"]

    if not to_resend and not to_clear_only:
        return

    print(f"\n[Retry pass] {len(to_resend)} ارسال ناموفق، "
          f"{len(to_clear_only)} پاک‌کردن ناموفق - در حال تلاش دوباره (موازی)...")

    resend_groups = _group_by_contact(_results_to_recipients(to_resend))
    clear_only_groups = _group_by_contact(_results_to_recipients(to_clear_only))

    async def _open_isolated_page(worker_id, phase):
        try:
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(DEFAULT_ACTION_TIMEOUT_MS)
            await page.goto("https://chat.5040.me/")
            await login(page)
            return context, page
        except Exception as e:
            print(f"[Retry-{phase} تب {worker_id}] لاگین/باز کردن صفحه شکست خورد: {e}")
            return None, None

    async def resend_worker(chunk, worker_id):
        context, page = await _open_isolated_page(worker_id, "ارسال")
        if page is None:
            return

        for group in chunk:
            contact_name = group["contact"]
            try:
                results = await process_contact_group(page, contact_name, group["messages"],
                                                        clear_after_send=clear_after_send)
            except Exception as e:
                print(f"[Retry-ارسال تب {worker_id}] خطای غیرمنتظره روی «{contact_name}»: {e}")
                await _recover_page_after_failure(page)
                continue

            for result in results:
                status_word = "OK" if result["send_status"] == "موفق" else "FAILED"
                print(f"[Retry ارسال] {contact_name} - {status_word}")
                if on_result:
                    on_result(_normalize_result(result))

        try:
            await page.close()
        except Exception:
            pass
        try:
            await context.close()
        except Exception:
            pass

    async def clear_worker(chunk, worker_id):
        context, page = await _open_isolated_page(worker_id, "پاک‌کردن")
        if page is None:
            return

        for group in chunk:
            contact_name = group["contact"]
            start_time = datetime.now()
            clear_status, clear_error = "موفق", ""

            try:
                await open_chat(page, contact_name)
                await clear_current_chat_history(page)
            except Exception as e:
                clear_status = "ناموفق"
                clear_error = str(e)
                await _recover_page_after_failure(page)

            print(f"[Retry پاک‌کردن] {contact_name} - {'OK' if clear_status == 'موفق' else 'FAILED'}")
            for m in group["messages"]:
                retry_result = {
                    "contact_name": contact_name,
                    "image_path": m.get("image"),
                    "caption": m.get("caption") or build_dynamic_text(),
                    "start_time": start_time,
                    "end_time": datetime.now(),
                    "duration": round((datetime.now() - start_time).total_seconds(), 2),
                    "send_status": "موفق (ارسال قبلی)",
                    "send_error": "",
                    "clear_status": clear_status,
                    "clear_error": clear_error,
                }
                if on_result:
                    on_result(_normalize_result(retry_result))

            await asyncio.sleep(INTERVAL_SECONDS)

        try:
            await page.close()
        except Exception:
            pass
        try:
            await context.close()
        except Exception:
            pass

    resend_chunks = _split_into_chunks(resend_groups, num_tabs)
    clear_chunks = _split_into_chunks(clear_only_groups, num_tabs)

    await asyncio.gather(
        *(resend_worker(chunk, i + 1) for i, chunk in enumerate(resend_chunks)),
        *(clear_worker(chunk, i + 1) for i, chunk in enumerate(clear_chunks)),
        return_exceptions=True,
    )


async def _send_batch_async(recipients: list, num_tabs: int = DEFAULT_NUM_TABS, clear_after_send: bool = True,
                             run_id: str = None, on_result=None):
    """
    ⚠️ هر تب (worker) الان BrowserContext کاملاً جدا و لاگین مستقل خودش رو
    داره (نه یه context/session مشترک برای همه‌ی تب‌ها). دلیلش: با context
    مشترک، چون localStorage/cookie بین تب‌های همون context به اشتراک میره،
    اگه سایت از localStorage برای «سینک کردن چت فعال بین تب‌های همون اکانت»
    استفاده کنه (رفتار رایج تو اپ‌های چت مثل واتساپ‌وب/تلگرام‌وب)، تب‌ها با
    هم تداخل پیدا می‌کنن (باز شدن چت تو یه تب، هدر تب دیگه رو هم عوض می‌کنه).
    با context جدا برای هر تب، این تداخل کاملاً از بین می‌ره - دقیقاً مثل
    اینکه هر تب رو یه مرورگر کاملاً جدا باز کرده باشی.

    ⚠️ Resume (بازنویسی‌شده 1405/06/25 - ببین core/runlog.py): اگه این batch
    (دقیقاً همین run_id) قبلاً یه‌بار شروع شده باشه و وسط کار (کرش/قطعی/بستن
    دستی) متوقف شده باشه، با اجرای دوباره‌ی همین run_id، کسایی که *موفق*
    پیام گرفته بودن خودکار skip می‌شن - این خودِ core.runlog.log_item() ثبت
    می‌کنه (فوری، flush شده)، نه یه فایل resume جدا.
    """
    component = "sender.v1"
    if run_id is None:
        run_id = _compute_run_id(recipients)   # فقط برای استفاده‌ی مستقل (__main__)

    already_done = runlog.resume_done_keys(run_id, component)

    if already_done:
        original_count = len(recipients)
        skipped, remaining = [], []
        for r in recipients:
            (skipped if _resume_key(r["contact"], r.get("caption")) in already_done else remaining).append(r)
        recipients = remaining
        print(f"[Resume] این batch قبلاً شروع شده بود (run_id={run_id}) - "
              f"{len(skipped)} نفر که قبلاً موفق پیام گرفتن رد شدن "
              f"({original_count} → {len(recipients)} نفر باقی‌مونده)")
        if on_result:
            for r in skipped:
                on_result({"ok": True, "resume_key": _resume_key(r["contact"], r.get("caption")),
                            "contact": r["contact"], "skipped": True, "known_contact": None})

    if not recipients:
        print("[Resume] همه‌ی این batch قبلاً با موفقیت ارسال شده - کاری برای انجام نیست")
        return

    print(f"[Async parallel] {num_tabs} تب کاملاً ایزوله (context/لاگین جدا)، {len(recipients)} مخاطب")

    total = len(recipients)
    durations = []
    counter = {"done": 0}
    batch_start = time.perf_counter()

    # گروه‌بندی بر اساس مقصد قبل از تقسیم بین تب‌ها - تضمین می‌کنه هر مقصد
    # مشترک (مثلاً یه کانال که چندتا خروجی گزارش می‌گیره) همیشه توسط دقیقاً
    # یک تب پردازش بشه، نه پخش بین چند تب ایزوله (ببین _group_by_contact)
    groups = _group_by_contact(recipients)
    chunks = _split_into_chunks(groups, num_tabs)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, channel="chrome")

        run_results = []   # نتایج همه‌ی این batch - برای retry pass در پایان

        async def worker(chunk, worker_id):
            try:
                context = await browser.new_context()   # ⚠️ context جدا و ایزوله برای این تب
                page = await context.new_page()
                page.set_default_timeout(DEFAULT_ACTION_TIMEOUT_MS)
                await page.goto("https://chat.5040.me/")
                await login(page)   # ⚠️ لاگین مستقل - نه استفاده از سشن مشترک
            except Exception as e:
                # اگه خودِ لاگین/باز کردن این تب شکست بخوره، این chunk رد
                # می‌شه ولی بقیه‌ی تب‌ها ادامه می‌دن - یه تب کرش‌شده نباید
                # کل batch رو متوقف کنه
                msg_count = sum(len(g["messages"]) for g in chunk)
                print(f"[تب {worker_id}] لاگین/باز کردن صفحه شکست خورد: {e} - "
                      f"{msg_count} پیام این تب رد شدن")
                return

            for group in chunk:
                contact_name = group["contact"]
                try:
                    results = await process_contact_group(page, contact_name, group["messages"],
                                                            clear_after_send=clear_after_send)
                except Exception as e:
                    # اگه پردازش یک مقصد به‌طور غیرمنتظره (نه فقط خطای ارسال
                    # عادی که خودش داخل process_contact_group گرفته می‌شه، بلکه
                    # کرش خودِ page/context) شکست بخوره، این یکی رو لاگ کن و
                    # برو سراغ مقصد بعدی - کل تب رو متوقف نکن
                    print(f"[تب {worker_id}] خطای غیرمنتظره روی «{contact_name}»: {e}")
                    continue

                for result in results:
                    durations.append(result["duration"])
                    counter["done"] += 1
                    print(format_result_line(counter["done"], total, result))
                    run_results.append(result)
                    if on_result:
                        on_result(_normalize_result(result))

            try:
                await page.close()
            except Exception:
                pass
            try:
                await context.close()   # کل context مخصوص این تب رو هم می‌بندیم
            except Exception:
                pass

        await asyncio.gather(
            *(worker(chunk, i + 1) for i, chunk in enumerate(chunks)),
            return_exceptions=True,   # کرش یک تب، بقیه‌ی تب‌ها رو متوقف نکنه
        )

        # ─── مرحله‌ی retry پایانی ───────────────────────────────────────────
        # بعد از تموم شدن کل batch: هرکی ارسالش ناموفق بود، از صفر (سرچ+ارسال+
        # پاک‌کردن) دوباره امتحان می‌شه؛ هرکی فقط پاک‌کردنش ناموفق بود، فقط
        # همون مرحله دوباره امتحان می‌شه (بدون ارسال دوباره‌ی پیام). این مرحله
        # هم context/لاگین مستقل خودش رو داره.
        await _retry_pass(browser, run_results, on_result, num_tabs, clear_after_send=clear_after_send)

        await browser.close()

    total_seconds = time.perf_counter() - batch_start
    average_seconds = sum(durations) / len(durations) if durations else 0.0
    print(f"\nTotal execution time: {total_seconds:.2f}s")
    print(f"Average time per contact: {average_seconds:.2f}s")


async def _send_batch_sequential_async(recipients: list, clear_after_send: bool = True):
    """حالت کاملاً ترتیبی (num_tabs=1) - برای دیباگ"""
    await _send_batch_async(recipients, num_tabs=1, clear_after_send=clear_after_send)


# ─── تابع اصلی - نقطه‌ی اتصال به Senders/payamresan.py ──────────────────────────
def send_message(rendered: list, agents_csv_path: str, num_tabs: int = DEFAULT_NUM_TABS,
                  clear_after_send: bool = True, run_id: str = None, on_result=None):
    """
    قرارداد Senders/payamresan.py: send_message(rendered, agents_csv_path, num_tabs, clear_after_send, run_id, on_result).
    rendered مستقیم از payamresan.send می‌آد. به‌صورت پیش‌فرض تا num_tabs تب هم‌زمان
    (concurrent، نه Thread) اجرا می‌شه تا مشکل سرعت حل بشه.

    clear_after_send: این فایل مرجع/مشترک بین چند پروژه‌ست. پروژه‌های ارسال
    انبوه (تعداد بالا) باید True بذارن (پیش‌فرض - رفتار قبلی) وگرنه اکانت
    سنگین می‌شه. پروژه‌هایی با تعداد کم در هر سیکل (مثل این پروژه که قرار
    نیست تعداد بالایی در هر سیکل بفرسته) باید صریحاً False پاس بدن.

    run_id/on_result (1405/06/25): ببین core/runlog.py. run_id=None فقط
    برای استفاده‌ی مستقل از این فایل (__main__ پایین همین فایل) پیش می‌آد -
    Senders/payamresan.py همیشه صریحاً run_id می‌فرسته.
    """
    if not rendered:
        print("لیست خالیه - هیچ پیامی برای ارسال نیست")
        return

    asyncio.run(_send_batch_async(rendered, num_tabs=num_tabs, clear_after_send=clear_after_send,
                                   run_id=run_id, on_result=on_result))


# ─── بلوک تست مستقل ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fake_rendered = [
        {"contact": "سید مهدی رضوان مدنی", "image": None, "caption": "تست ۱"},
        {"contact": "مریم رضایی", "image": None, "caption": "تست ۲"},
        {"contact": "محمدرسول طارمی", "image": None, "caption": "تست ۳"},
    ]
    send_message(fake_rendered, agents_csv_path="", num_tabs=2)