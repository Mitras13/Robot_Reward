# -*- coding: utf-8 -*-
"""
send_message_v2.py - نسخه‌ی مبتنی بر WS (کپی‌شده و یکپارچه‌شده از پروژه‌ی
مستقل Payamresan_sender_ws در 2026-09-15، ببین E:\\Payamresan_sender_ws\\DOCS.md
برای تاریخچه‌ی کامل کشف پروتکل و تست فشار). ارسال پیام متنی/عکس به پیام‌رسان
داخلی بدون کلیک روی UI و بدون ساخت اتصال خام پایتونی (که سرور به دلیل
fingerprint غیرمرورگری قطعش می‌کرد).

⚠️ فقط از طریق Senders/payamresan.py صدا زده می‌شه (فلگ config/sender_version.txt
== "2")، نه مستقیم - ببین payamresan.py برای معماری کامل سوییچ v1/v2.

قرارداد امضای مشترک با v1 (send_message.py) - این چیزی‌ست که payamresan.py
واقعاً صدا می‌زند:
    send_message(rendered, agents_csv_path="", num_tabs=1, clear_after_send=True, run_id=None)
    rendered = [{"contact", "image", "caption", "panel_user_id"?, "chat_user_id"?}, ...]
agents_csv_path نادیده گرفته می‌شه (دقیقاً همون دلیل v1 - نگه‌داشته‌شده فقط
برای هماهنگی امضا). num_tabs هم نادیده گرفته می‌شه - معماری این نسخه ذاتاً
سریاله (یک لاگین/session، نه چند تب هم‌زمان؛ اولویت ۲ - فعلاً لازم نیست،
تست فشار نشون داد سرعت سریالی همین‌جوریش هم بهتر از v1 کلیکی‌ست).
اگه یه آیتم `chat_user_id` داشته باشه (از یه دفترچه‌ی مخاطبین آینده که با
panel_user_id پر می‌شه - هنوز پیاده نشده)، مستقیم باهاش می‌فرسته (بدون سرچ)؛
وگرنه از `contact` (اسم) با همون مسیر سرچ+کش همیشگی استفاده می‌کنه.

روش: با Playwright یه مرورگر واقعی (قابل headless) لاگین می‌کنیم، ولی به
هیچ دکمه‌ای کلیک نمی‌کنیم. قبل از لود شدن اپ، سازنده‌ی window.WebSocket رو
هوک می‌کنیم تا همون WebSocket واقعی‌ای که خودِ اپ بعد از لاگین می‌سازه رو در
اختیار بگیریم و مستقیماً روش فریم‌های پروتکل PM3.0 رد و بدل کنیم. چون از
سوکت واقعیِ خودِ مرورگر استفاده می‌کنیم، هیچ مسدودسازی‌ای در کار نیست.

دو سناریوی ارسال:
    ۱. مستقیم با username/id شناخته‌شده - بدون هیچ جستجویی (فیلد "session"
       رو از پروتکل واقعی PezhvaClient.sendText بررسی کردیم: کاملاً اختیاریه،
       با username به‌تنهایی هم پیام درست تحویل داده می‌شه).
    ۲. جستجو در کل دایرکتوری شرکت (req="search_dir") وقتی فقط اسم رو داریم -
       برخلاف get_subscribed_users که فقط مخاطبین/چت‌های موجودت رو می‌گرده،
       search_dir کل شرکت رو می‌گرده (حتی کسایی که تا حالا باهاشون چت نداشتی).

⚠️ کانفیگ: یوزرنیم/پسورد از فایل .env (که تو .gitignore هست، هیچ‌وقت commit
نمی‌شه) خونده می‌شه. یه نسخه‌ی نمونه‌ش رو تو .env.example ببین.

clear_after_send (کشف‌شده و پیاده‌شده 2026-09-15): بعد از ارسال هر پیام، اگه
True باشه، تاریخچه‌ی مکالمه (فقط سمت خودمون، نه سمت مخاطب) پاک می‌شه - چون
حجم بالای پیام‌های ارسالی روی اکانت جمع می‌شه و اگه بعداً یه انسان بخواد با
همین اکانت لاگین کند و وضعیت رو چک کند، مرورگرش کرش می‌کند. دقیقاً همون
دلیلی که send_message.py (نسخه‌ی کلیکی v1) این قابلیت رو داشت.

پروتکل کشف‌شده (با sniff_clear.py، از شنود ترافیک واقعی):
    درخواست:  {"req": "clear_msg_history", "headers": [{"key": "session",
               "value": "<SessionId مخاطب>"}], ...}
    پاسخ موفق: flags="SUCCESS", body="MESSAGS_DELETED" (تایپوی خودِ سرور).

SessionId (نه username/id مخاطب - یه شناسه‌ی عددی جدای مکالمه) فقط از
get_subscribed_users یا از پوش سرور بعد از sub_user در دسترسه؛ برای مخاطب
کاملاً تازه (که هیچ‌وقت باهاش چت نداشتی) باید اول sub_user بفرستیم تا سرور
SessionId تازه رو با یه پوش (req="get_subscribed_users" بدون ref) بفرسته.
فقط برای اشخاص پیاده‌شده - برای گروه/کانال (is_entity=True) فعلاً clear رد
می‌شه (تست/کشف نشده، اولویت ۲).
"""

import asyncio
import base64
import json
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from core import runlog
from . import contact_cache

# مسیر صریح، نه پیش‌فرض find_dotenv() - چون این فایل تو Senders/ زندگی می‌کند
# ولی main.py معمولاً از ریشه‌ی پروژه اجرا می‌شه؛ اکتشاف پیش‌فرض
# dotenv (بر اساس frame فراخوان) بسته به اینکه چطور import شده می‌تونه فایل
# رو تو Senders/.env پیدا نکنه - مسیر صریح این ابهام رو کاملاً حذف می‌کنه.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def _now_str() -> str:
    """ساعت:دقیقه:ثانیه.میلی‌ثانیه دقیق لحظه‌ی ارسال - برای لاگ‌گیری"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


USERNAME = os.environ.get("PEZHVA_USERNAME")
PASSWORD = os.environ.get("PEZHVA_PASSWORD")
if not USERNAME or not PASSWORD:
    raise RuntimeError(
        "PEZHVA_USERNAME و PEZHVA_PASSWORD باید تو فایل .env یا متغیرهای محیطی ست بشن "
        "(نمونه‌ش تو .env.example هست)"
    )

LOGIN_URL = "https://chat.5040.me/"
WS_URL_SUBSTR = "PezhvaMessageBroker"

HEADLESS = True
DEFAULT_TIMEOUT_MS = 15000

# اسکریپتی که قبل از لود هر صفحه اجرا می‌شه: سازنده‌ی WebSocket رو هوک
# می‌کنه تا هر اتصالی که به آدرس PezhvaMessageBroker باز بشه (توسط خودِ اپ)
# رو ضبط کنه: هم خودِ instance (برای send)، هم لاگ کامل پیام‌های رد و بدل شده
# (برای اینکه بعداً بتونیم منتظر پاسخ بمونیم)، هم session-key/ftt کانکشن که
# فقط برای آپلود فایل لازمه (نه برای ارسال متن).
#
# ⚠️ MAX_FRAMES: تو ارسال‌های حجیم (مثلاً ۳۰۰۰ پیام) اگه این آرایه رو بی‌نهایت
# نگه داریم، هم حافظه‌ی مرورگر پر می‌شه هم waitForRef (که هر بار کل آرایه رو
# اسکن می‌کنه) کند می‌شه. چون فقط به آخرین چند صد فریم برای پیدا کردن پاسخ
# درخواست‌های در حال انتظار نیاز داریم (پاسخ‌ها معمولاً در کسری از ثانیه
# می‌رسن)، آرایه رو به یه سقف ثابت محدود می‌کنیم و قدیمی‌ترین‌ها رو دور می‌ریزیم.
_HOOK_SCRIPT = """
(() => {
    window.__wsFrames = [];
    window.__capturedWS = null;
    window.__pezhvaSession = null;
    const MAX_FRAMES = 1000;
    const pushFrame = (frame) => {
        window.__wsFrames.push(frame);
        if (window.__wsFrames.length > MAX_FRAMES) {
            window.__wsFrames.splice(0, window.__wsFrames.length - MAX_FRAMES);
        }
    };
    const NativeWebSocket = window.WebSocket;
    window.WebSocket = new Proxy(NativeWebSocket, {
        construct(target, args) {
            const url = args[0] || "";
            const instance = new target(...args);
            if (String(url).includes("%s")) {
                window.__capturedWS = instance;
                instance.addEventListener("message", (ev) => {
                    pushFrame({ dir: "in", data: ev.data, t: Date.now() });
                    try {
                        const parsed = JSON.parse(ev.data);
                        if (parsed.req === "reg" && parsed.flags === "SUCCESS") {
                            const getHeader = (k) => (parsed.headers || []).find(h => h.key === k)?.value || null;
                            window.__pezhvaSession = {
                                sessionKey: getHeader("session-key"),
                                ftt: getHeader("ftt"),
                            };
                        }
                    } catch (e) {}
                });
                const originalSend = instance.send.bind(instance);
                instance.send = (data) => {
                    pushFrame({ dir: "out", data: data, t: Date.now() });
                    return originalSend(data);
                };
            }
            return instance;
        }
    });
})();
""" % WS_URL_SUBSTR

# کمک‌تابع‌های مشترک جاوااسکریپت (key سازی + منتظرماندن برای پاسخ متناظر با
# یه key، از روی فیلد ref) - در همه‌ی اسکریپت‌های ارسال/جستجو تکرار می‌شه
_JS_HELPERS = """
function makeKey(tsStr) {
    const rnd = Math.floor(100 + Math.random() * 900);
    return `${rnd}${tsStr.slice(-9)}`;
}
function waitForRef(key, timeoutMs) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        const seen = new Set();
        const check = () => {
            for (const frame of window.__wsFrames) {
                if (frame.dir !== "in" || seen.has(frame)) continue;
                seen.add(frame);
                let parsed;
                try { parsed = JSON.parse(frame.data); } catch (e) { continue; }
                if (parsed.ref === key) { resolve(parsed); return; }
            }
            if (Date.now() - start > timeoutMs) {
                reject(new Error("timeout waiting for ref=" + key));
                return;
            }
            setTimeout(check, 100);
        };
        check();
    });
}
"""

# جستجوی کل دایرکتوری شرکت (نه فقط مخاطبین موجود) - همون req ای که سایت با
# تایپ‌کردن تو باکس سرچ می‌فرسته
_SEARCH_DIR_JS = """
async ({ fromUsername, searchTerm, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "req",
        key, ts, req: "search_dir", from: fromUsername,
        headers: [
            { key: "token", value: searchTerm },
            { key: "info", value: "true" }
        ]
    }));
    const reply = await waitForRef(key, timeoutMs);
    if (reply.flags !== "SUCCESS") throw new Error("جستجو شکست خورد: " + JSON.stringify(reply));

    const parsed = JSON.parse(reply.body || "{}");
    return Object.values(parsed).map(u => ({ Username: u.Username, Alias: u.Alias, IsEntity: false }));
}
"""

# جستجوی گروه‌ها/کانال‌های کل شرکت (نه فقط اونایی که عضوشونی) - معادل
# search_dir ولی برای entity ها (searchEntityDirectory تو کد خودِ اپ)
_SEARCH_ENTITY_DIR_JS = """
async ({ fromUsername, searchTerm, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "req",
        key, ts, req: "search_entity_dir", from: fromUsername,
        headers: [
            { key: "token", value: searchTerm },
            { key: "info", value: "true" }
        ]
    }));
    const reply = await waitForRef(key, timeoutMs);
    if (reply.flags !== "SUCCESS") throw new Error("جستجوی گروه/کانال شکست خورد: " + JSON.stringify(reply));

    const parsed = JSON.parse(reply.body || "[]");
    return parsed.map(e => ({ Username: e.key, Alias: e.alias, IsEntity: true }));
}
"""

# گروه‌های خصوصی (برخلاف کانال‌های عمومی) تو دایرکتوری کل شرکت قابل‌جستجو
# نیستن - فقط اعضاشون می‌بینتشون. برای این‌ها باید لیست get_subscribed_entities
# (چیزی که خودت عضوشی) رو گرفت و محلی فیلتر کرد.
_SEARCH_SUBSCRIBED_ENTITIES_JS = """
async ({ fromUsername, searchTerm, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "req",
        key, ts, req: "get_subscribed_entities", from: fromUsername
    }));
    const reply = await waitForRef(key, timeoutMs);
    if (reply.flags !== "SUCCESS") throw new Error("گرفتن لیست گروه/کانال‌های عضو شکست خورد: " + JSON.stringify(reply));

    const parsed = JSON.parse(reply.body || "[]");
    const term = searchTerm.trim();
    return parsed
        .filter(e => (e.Alias || "").includes(term) || e.Username === term)
        .map(e => ({ Username: e.Username, Alias: e.Alias, IsEntity: true }));
}
"""

# مخاطبین شخصی‌ای که قبلاً باهاشون چت داشتی (get_subscribed_users) - برخلاف
# search_dir (دایرکتوری عمومی)، این لیست فلگ IsDeactive رو هم داره. چون
# search_dir اکانت‌های غیرفعال رو اصلاً نشون نمی‌ده (تست شد)، تنها راه فهمیدن
# «این آدم قبلاً مخاطبم بوده ولی الان غیرفعال شده» همین لیسته.
_SEARCH_SUBSCRIBED_USERS_JS = """
async ({ fromUsername, searchTerm, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "req",
        key, ts, req: "get_subscribed_users", from: fromUsername
    }));
    const reply = await waitForRef(key, timeoutMs);
    if (reply.flags !== "SUCCESS") throw new Error("گرفتن لیست مخاطبین شکست خورد: " + JSON.stringify(reply));

    const parsed = JSON.parse(reply.body || "[]");
    const term = searchTerm.trim();
    return parsed
        .filter(u => (u.Alias || "").includes(term) || u.Username === term)
        .map(u => ({ Username: u.Username, Alias: u.Alias, IsEntity: false, IsDeactive: !!u.IsDeactive,
                     SessionId: u.SessionId || null }));
}
"""

# ارسال مستقیم پیام متنی - بدون هیچ lookup ای، فقط با username/id شناخته‌شده.
# isEntity=true وقتی مقصد گروه/کانال باشه (نه یک شخص) - هدر "entity" رو
# طبق sendText واقعی PezhvaClient اضافه می‌کنه، وگرنه سرور NOT_PERMITTED
# یا خطای مسیریابی می‌ده.
_SEND_TEXT_JS = """
async ({ fromUsername, toUsername, text, isEntity, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");

    const headers = [
        { key: "type", value: "1" },
        { key: "contentType", value: "text" },
        { key: "notification", value: JSON.stringify({ type: "txt", url: "", content: text }) }
    ];
    if (isEntity) headers.push({ key: "entity", value: toUsername });

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "txt",
        key, ts, from: fromUsername, to: toUsername, headers, body: text
    }));
    const reply = await waitForRef(key, timeoutMs);
    if (reply.flags === "ERROR") throw new Error("ارسال رد شد: " + (reply.body || JSON.stringify(reply)));
    if (reply.body !== "MESSAGE_SENT") throw new Error("ارسال تایید نشد: " + JSON.stringify(reply));

    return {
        ok: true,
        to: toUsername,
        repoId: (reply.headers || []).find(h => h.key === "repoId")?.value || null
    };
}
"""

# ارسال عکس+کپشن به یک username/id مستقیم (بدون lookup مخاطب). فقط برای
# خودِ آپلود فایل، session-key کانکشن (نه SessionId مخاطب) لازمه. isEntity
# همون منطق هدر "entity" برای گروه/کانال رو داره (ببین _SEND_TEXT_JS)
_SEND_IMAGE_JS = """
async ({ fromUsername, toUsername, caption, fileBase64, fileName, isEntity, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");
    if (!window.__pezhvaSession || !window.__pezhvaSession.sessionKey) {
        throw new Error("session-key کانکشن هنوز دریافت نشده");
    }
    const { sessionKey, ftt } = window.__pezhvaSession;

    const byteChars = atob(fileBase64);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
    const byteArray = new Uint8Array(byteNumbers);
    const ext = (fileName.split(".").pop() || "").toLowerCase();
    const mime = { png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp" }[ext] || "application/octet-stream";
    const blob = new Blob([byteArray], { type: mime });

    const formData = new FormData();
    formData.append("file", blob, fileName);

    const uploadUrl = `https://chat.5040.me/FileUpload?app=darkoob&session=${encodeURIComponent(sessionKey)}&category=misc`;
    const uploadResp = await fetch(uploadUrl, { method: "POST", body: formData, credentials: "include" });
    if (!uploadResp.ok) throw new Error("آپلود فایل شکست خورد: HTTP " + uploadResp.status);
    const uploadedFileName = (await uploadResp.text()).trim();

    const lastSlash = uploadedFileName.lastIndexOf("/");
    const dir = lastSlash >= 0 ? uploadedFileName.slice(0, lastSlash + 1) : "";
    const base = lastSlash >= 0 ? uploadedFileName.slice(lastSlash + 1) : uploadedFileName;
    const dotIdx = base.lastIndexOf(".");
    const thumbBase = dotIdx >= 0 ? base.slice(0, dotIdx) + "-thumb" + base.slice(dotIdx) : base + "-thumb";
    const thumbUrl = `https://chat.5040.me/uploaded/Misc/${dir}${thumbBase}?ftt=${ftt}&null=null`;

    const headers = [
        { key: "type", value: "2" },
        { key: "contentType", value: "image" },
        { key: "filename", value: fileName },
        { key: "filesize", value: byteArray.length },
        { key: "notification", value: JSON.stringify({ type: "file", url: thumbUrl, content: (caption || "") + "\\r\\n" + fileName }) }
    ];
    if (isEntity) headers.push({ key: "entity", value: toUsername });

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "txt",
        key, ts, from: fromUsername, to: toUsername, headers,
        body: JSON.stringify({ fileName: uploadedFileName, caption: caption || undefined }),
        waitForSend: false
    }));
    const reply = await waitForRef(key, timeoutMs);
    if (reply.flags === "ERROR") throw new Error("ارسال رد شد: " + (reply.body || JSON.stringify(reply)));
    if (reply.body !== "MESSAGE_SENT") throw new Error("ارسال تایید نشد: " + JSON.stringify(reply));

    return {
        ok: true,
        to: toUsername,
        uploadedFileName,
        repoId: (reply.headers || []).find(h => h.key === "repoId")?.value || null
    };
}
"""

# ارسال یک فایل غیرتصویری (اکسل/CSV/...) به‌عنوان پیوست قابل‌دانلود - اضافه
# شده ۲۰۲۶-۰۹-۲۲ طبق درخواست کاربر ("اضافه کن که بشه اکسل یا CSV هم به غیر
# از متن و عکس ارسال کرد")، عمداً یک تابع/JS کاملاً جدا از _SEND_IMAGE_JS
# بالا (کپی با یک خط فرق) نه ویرایش همون تابع - طبق تصمیم صریح کاربر که
# رفتار ارسال عکس فعلی دست‌نخورده بمونه.
#
# ⚠️ مقادیر headers.type/contentType اینجا حدسی‌ان، نه کشف‌شده از پروتکل
# واقعی (کاربر صریحاً گفت "نمی‌دونم - حدس بزن و تست کن" ۲۰۲۶-۰۹-۲۲). تاریخچه‌ی
# تست‌های واقعی همون روز:
#   تلاش ۱: type="2" (همون type عکس)، contentType="file" -> بازم به‌صورت
#     عکس نمایش داده شد (یعنی contentType رو کلاینت برای تصمیم عکس/فایل
#     استفاده نمی‌کنه، یا حداقل تنها عامل نیست).
#   تلاش ۲: type="3" -> به‌صورت پیام صوتی (VOICE) فرستاده شد! یعنی
#     headers.type واقعاً enum نوع پیامه، نه یه فیلد بی‌اثر - الگوی محتمل:
#     1=متن، 2=عکس، 3=صدا.
#   تلاش ۳ (فعلی): type="5" - با فرض که 4 به ویدیو تعلق داره و 5 فایل
#     عمومیه؛ کاملاً حدسیه، تأیید نشده.
# اگه تلاش ۳ هم غلط بود، طبق تصمیم کاربر ۲۰۲۶-۰۹-۲۲ دیگه نباید کورکورانه
# عدد بعدی رو روی یک مخاطب واقعی تست کرد - باید ترافیک واقعی یک ارسال فایل
# از کلاینت رسمی sniff بشه (کاربر DevTools رو باز کنه، یک فایل واقعی بفرسته،
# و فریم WS واقعی رو بده تا از روش کپی بشه - دقیقاً همون روشی که خود
# type="2"/عکس کشف شده بود).
_SEND_FILE_JS = """
async ({ fromUsername, toUsername, caption, fileBase64, fileName, isEntity, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");
    if (!window.__pezhvaSession || !window.__pezhvaSession.sessionKey) {
        throw new Error("session-key کانکشن هنوز دریافت نشده");
    }
    const { sessionKey, ftt } = window.__pezhvaSession;

    const byteChars = atob(fileBase64);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: "application/octet-stream" });

    const formData = new FormData();
    formData.append("file", blob, fileName);

    const uploadUrl = `https://chat.5040.me/FileUpload?app=darkoob&session=${encodeURIComponent(sessionKey)}&category=misc`;
    const uploadResp = await fetch(uploadUrl, { method: "POST", body: formData, credentials: "include" });
    if (!uploadResp.ok) throw new Error("آپلود فایل شکست خورد: HTTP " + uploadResp.status);
    const uploadedFileName = (await uploadResp.text()).trim();

    const lastSlash = uploadedFileName.lastIndexOf("/");
    const dir = lastSlash >= 0 ? uploadedFileName.slice(0, lastSlash + 1) : "";
    const base = lastSlash >= 0 ? uploadedFileName.slice(lastSlash + 1) : uploadedFileName;
    const dotIdx = base.lastIndexOf(".");
    const thumbBase = dotIdx >= 0 ? base.slice(0, dotIdx) + "-thumb" + base.slice(dotIdx) : base + "-thumb";
    const thumbUrl = `https://chat.5040.me/uploaded/Misc/${dir}${thumbBase}?ftt=${ftt}&null=null`;

    const headers = [
        { key: "type", value: "5" },
        { key: "contentType", value: "file" },
        { key: "filename", value: fileName },
        { key: "filesize", value: byteArray.length },
        { key: "notification", value: JSON.stringify({ type: "file", url: thumbUrl, content: (caption || "") + "\\r\\n" + fileName }) }
    ];
    if (isEntity) headers.push({ key: "entity", value: toUsername });

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "txt",
        key, ts, from: fromUsername, to: toUsername, headers,
        body: JSON.stringify({ fileName: uploadedFileName, caption: caption || undefined }),
        waitForSend: false
    }));
    const reply = await waitForRef(key, timeoutMs);
    if (reply.flags === "ERROR") throw new Error("ارسال رد شد: " + (reply.body || JSON.stringify(reply)));
    if (reply.body !== "MESSAGE_SENT") throw new Error("ارسال تایید نشد: " + JSON.stringify(reply));

    return {
        ok: true,
        to: toUsername,
        uploadedFileName,
        repoId: (reply.headers || []).find(h => h.key === "repoId")?.value || null
    };
}
"""

# پسوندهایی که همچنان از مسیر عکس همیشگی (_SEND_IMAGE_JS، contentType=
# "image") رد می‌شن - یعنی رفتار امروز برای عکس‌ها کاملاً دست‌نخورده می‌مونه؛
# هر پسوند دیگه‌ای (اکسل/CSV/PDF/...) از مسیر جدید _SEND_FILE_JS می‌ره.
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _is_image_path(path: str) -> bool:
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    return ext in _IMAGE_EXTENSIONS


# گرفتن SessionId مخاطب (شناسه‌ی عددی مکالمه، نه username/id) - لازم برای
# clear_msg_history. sub_user باعث می‌شه سرور یه پیام push (نه یه پاسخ مستقیم
# با ref - شبیه یه get_subscribed_users خودکار) بفرسته که SessionId مخاطب
# (چه تازه باشه چه قدیمی) توش هست؛ منتظرش می‌مونیم و از توش username مورد
# نظر رو پیدا می‌کنیم. برای مخاطب کاملاً تازه (اولین پیام)، همین پوش SessionId
# تازه‌ساخته‌شده رو هم برمی‌گردونه (کشف‌شده با sniff_clear.py).
_SUB_USER_SESSION_JS = """
async ({ fromUsername, username, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "req",
        key, ts, req: "sub_user", from: fromUsername,
        headers: [{ key: "usernames", value: username }]
    }));

    const start = Date.now();
    const seen = new Set();
    while (Date.now() - start < timeoutMs) {
        for (const frame of window.__wsFrames) {
            if (frame.dir !== "in" || seen.has(frame)) continue;
            seen.add(frame);
            let parsed;
            try { parsed = JSON.parse(frame.data); } catch (e) { continue; }
            if (parsed.req !== "get_subscribed_users" || !parsed.body) continue;
            let arr;
            try { arr = JSON.parse(parsed.body); } catch (e) { continue; }
            if (!Array.isArray(arr)) continue;
            const match = arr.find(u => u.Username === username);
            if (match && match.SessionId) return match.SessionId;
        }
        await new Promise(r => setTimeout(r, 100));
    }
    throw new Error("SessionId «" + username + "» بعد از sub_user پیدا نشد (timeout)");
}
"""

# پاک‌کردن تاریخچه‌ی مکالمه (فقط سمت خودمون) - پروتکل کشف‌شده با sniff_clear.py.
# clear_after_send رو با این پیاده می‌کنیم - ببین توضیح بالای فایل.
_CLEAR_HISTORY_JS = """
async ({ fromUsername, sessionId, timeoutMs }) => {
""" + _JS_HELPERS + """
    const ws = window.__capturedWS;
    if (!ws || ws.readyState !== 1) throw new Error("WebSocket آماده نیست");

    const ts = String(Date.now());
    const key = makeKey(ts);
    ws.send(JSON.stringify({
        ver: "PM3.0", app: "darkoob", type: "req",
        key, ts, req: "clear_msg_history", from: fromUsername,
        headers: [{ key: "session", value: String(sessionId) }]
    }));
    const reply = await waitForRef(key, timeoutMs);
    if (reply.flags !== "SUCCESS" || reply.body !== "MESSAGS_DELETED") {
        throw new Error("پاک‌کردن مکالمه تایید نشد: " + JSON.stringify(reply));
    }
    return true;
}
"""


async def _login(page):
    await page.locator('input[type="text"]').click()
    await page.locator('input[type="text"]').fill(USERNAME)
    await page.locator('input[type="password"]').click()
    await page.locator('input[type="password"]').fill(PASSWORD)
    await page.locator('input[type="password"]').press("Enter")
    await page.wait_for_load_state("networkidle")


async def _wait_for_ws_ready(page, timeout_ms: int = 20000):
    await page.wait_for_function(
        "() => window.__capturedWS && window.__capturedWS.readyState === 1",
        timeout=timeout_ms,
    )


async def _open_session(browser, need_upload_session: bool = False):
    """یه تب لاگین‌شده و WebSocket-hook-شده برمی‌گردونه، آماده‌ی ارسال درخواست"""
    context = await browser.new_context()
    page = await context.new_page()
    await page.add_init_script(_HOOK_SCRIPT)
    await page.goto(LOGIN_URL)
    await _login(page)
    await _wait_for_ws_ready(page)
    if need_upload_session:
        await page.wait_for_function(
            "() => window.__pezhvaSession && window.__pezhvaSession.sessionKey",
            timeout=15000,
        )
    return context, page


class DeactivatedContactError(Exception):
    """وقتی مخاطب/گروه/کانال هدف غیرفعاله - ارسال به‌طور دائم شکست می‌خوره،
    پس اصلاً نباید تلاش کرد (نه الان، نه تو اجراهای بعدی همین run_id)"""
    pass


# نگاشت حروف عربی به معادل فارسی‌شون + کاراکترهای نامرئی رایج (نیم‌فاصله،
# نشانگرهای RTL/LTR) - پورت‌شده از send_message.py (v1)، چون بعضی اسامی با
# کیبورد عربی، بعضی با فارسی تایپ شدن
_ARABIC_TO_PERSIAN_MAP = str.maketrans({
    "ي": "ی",
    "ك": "ک",
    "ة": "ه",
    "أ": "ا",
    "إ": "ا",
    "ؤ": "و",
    "ئ": "ی",
    "‌": " ",
    "‏": "",
    "‎": "",
})


def _normalize_whitespace(text: str) -> str:
    """چند فاصله‌ی پشت‌سرهم رو یکی می‌کنه + trim - برای مقایسه/سرچ fallback"""
    return re.sub(r"\s+", " ", text).strip()


def _strip_english_suffix(name: str) -> str:
    """پسوند انگلیسی انتهای اسم (مثل VP/RW/NP) رو حذف می‌کنه - این پسوند از
    داده‌ی خام فروش میاد، نه از دایرکتوری واقعی پیام‌رسان (که یا اصلاً نداردش
    یا فاصله‌گذاری/مقدارش فرق داره) - برای همین سرچ با رشته‌ی کامل شکست
    می‌خوره. ببین: باگ «عدم تحویل پیام برای مخاطبین با پسوند تیم» (۲۰۲۶-۰۹-۱۹)."""
    stripped = re.sub(r"\s*[A-Za-z]+\s*$", "", name)
    return _normalize_whitespace(stripped)


def _normalize_name_fully(name: str) -> str:
    """نرمال‌سازی جامع اسم برای fallback سرچ - عربی->فارسی + فاصله‌های اضافه
    + حذف پسوند انگلیسی انتهای اسم. پورت‌شده از send_message.py (v1).

    ⚠️ ریسک پذیرفته‌شده (عیناً همونی که v1 قبلاً پذیرفته): اگه دو نفر دقیقاً
    هم‌اسم فارسی باشن (فقط پسوندشون فرق کنه)، ممکنه با هم اشتباه گرفته بشن."""
    text = name.translate(_ARABIC_TO_PERSIAN_MAP)
    text = _strip_english_suffix(text)
    text = _normalize_whitespace(text)
    return text


async def _search_all(page, name: str) -> list:
    """جستجوی ترکیبی: افراد (search_dir) + کانال‌های عمومی (search_entity_dir) +
    گروه‌های خصوصی‌ای که خودت عضوشونی (get_subscribed_entities) + مخاطبین
    شخصی‌ای که قبلاً باهاشون چت داشتی (get_subscribed_users) - این آخری به این
    خاطر لازمه که search_dir اکانت‌های غیرفعال رو اصلاً نشون نمی‌ده؛ تنها راه
    فهمیدن «قبلاً مخاطبم بود ولی الان غیرفعال شده» همین لیسته."""
    users, public_entities, private_entities, subscribed_users = await asyncio.gather(
        page.evaluate(_SEARCH_DIR_JS, {"fromUsername": USERNAME, "searchTerm": name, "timeoutMs": DEFAULT_TIMEOUT_MS}),
        page.evaluate(_SEARCH_ENTITY_DIR_JS, {"fromUsername": USERNAME, "searchTerm": name, "timeoutMs": DEFAULT_TIMEOUT_MS}),
        page.evaluate(_SEARCH_SUBSCRIBED_ENTITIES_JS, {"fromUsername": USERNAME, "searchTerm": name, "timeoutMs": DEFAULT_TIMEOUT_MS}),
        page.evaluate(_SEARCH_SUBSCRIBED_USERS_JS, {"fromUsername": USERNAME, "searchTerm": name, "timeoutMs": DEFAULT_TIMEOUT_MS}),
    )
    seen = set()
    combined = []
    # subscribed_users آخر از همه چک می‌شه که اگه یکی هم تو search_dir (فعال)
    # هم تو subscribed (با IsDeactive) بود، نسخه‌ی فعال (اولی) اولویت داره.
    # dedup روی Username.lower() چون همون آدم از دو منبع سرچ مختلف می‌تونه با
    # کیس متفاوت برگرده (مثلاً REMOTE318467 از یکی، remote318467 از یکی دیگه) -
    # قبلاً با تطبیق حساس به کیس دو ورودی جدا می‌موند و «چند نتیجه پیدا شد»
    # می‌داد، با اینکه واقعاً یک نفر بود.
    for m in users + public_entities + private_entities + subscribed_users:
        key = m["Username"].lower()
        if key in seen:
            continue
        seen.add(key)
        m.setdefault("IsDeactive", False)
        combined.append(m)
    return combined


async def search_directory_via_browser(name: str, headless: bool = HEADLESS) -> list:
    """جستجوی کل دایرکتوری شرکت - هم افراد هم گروه/کانال‌ها - بر اساس اسم/بخشی از اسم"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser)
        matches = await _search_all(page, name)
        await browser.close()
        return matches


def search_directory(name: str, headless: bool = HEADLESS) -> list:
    return asyncio.run(search_directory_via_browser(name, headless=headless))


def _resolve_single_match(matches: list, name: str, original_name: str = None) -> dict:
    display_name = original_name or name
    if not matches:
        raise LookupError(f"هیچ مخاطب/گروه/کانالی با «{display_name}» تو دایرکتوری شرکت پیدا نشد")
    exact = [m for m in matches if m["Username"] == name or m["Alias"] == name]
    if len(exact) == 1:
        return exact[0]
    if len(matches) > 1:
        options = "، ".join(f'{m["Alias"]} ({m["Username"]})' for m in matches)
        raise LookupError(f"چند نتیجه با «{display_name}» پیدا شد، دقیق‌تر مشخص کن: {options}")
    return matches[0]


async def _resolve_contact(page, name: str) -> dict:
    """اول تو جدول محلی مخاطبین (contact_cache) نگاه می‌کنه؛ اگه قبلاً یه‌بار
    با همین اسم یه نتیجه‌ی یکتا پیدا و ذخیره شده بود، بدون هیچ سرچ جدیدی
    همون رو برمی‌گردونه. فقط در صورت نبودن تو کش، جستجوی واقعی رو انجام
    می‌ده و نتیجه رو برای دفعه‌های بعد ذخیره می‌کنه.

    ⚠️ اگه مخاطب/گروه/کانال هدف غیرفعال باشه (IsDeactive)، اصلاً برنمی‌گرده -
    DeactivatedContactError پرتاب می‌شه تا هیچ تلاش ارسالی (نه الان نه بعداً)
    انجام نشه. این وضعیت هم تو کش ثبت می‌شه تا دفعه‌های بعد حتی نیاز به سرچ
    دوباره هم نباشه."""
    cached = contact_cache.get(name)
    if cached:
        if cached.get("is_deactive"):
            raise DeactivatedContactError(f"«{name}» ({cached['username']}) غیرفعاله - از کش رد شد، تلاشی نشد")
        return {"Username": cached["username"], "Alias": cached["alias"], "IsEntity": cached["is_entity"],
                "FromCache": True}

    matches = await _search_all(page, name)
    lookup_name = name
    if not matches:
        # Fallback: پسوند تیم (VP/RW/NP/...) از داده‌ی خام فروش میاد و اغلب
        # با دایرکتوری واقعی پیام‌رسان (فاصله‌گذاری/مقدار) نمی‌خونه - سرچ خام
        # هیچی برنمی‌گردونه. ببین: باگ «عدم تحویل پیام برای مخاطبین با پسوند
        # تیم» (۲۰۲۶-۰۹-۱۹) - همون fallback ی که v1 از قبل داره.
        fallback_name = _normalize_name_fully(name)
        if fallback_name and fallback_name != name:
            matches = await _search_all(page, fallback_name)
            lookup_name = fallback_name
    contact = _resolve_single_match(matches, lookup_name, original_name=name)
    contact_cache.put(name, contact["Username"], contact["Alias"], contact["IsEntity"], contact.get("IsDeactive", False))
    contact["FromCache"] = False
    if contact.get("IsDeactive"):
        raise DeactivatedContactError(f"«{name}» ({contact['Username']}) غیرفعاله - تلاشی برای ارسال نشد")
    return contact


async def _resolve_session_id(page, contact: dict):
    """SessionId مخاطب (نه username/id - شناسه‌ی عددی خودِ مکالمه) رو برمی‌گردونه،
    فقط لازم برای clear_msg_history. فقط برای اشخاص - برای گروه/کانال None
    برمی‌گردونه (کشف/تست نشده - ببین docstring بالای فایل).

    اول تو contact_cache نگاه می‌کنه؛ نبود، با sub_user درخواستش می‌کنه (که
    هم برای مخاطب قدیمی هم کاملاً تازه کار می‌کنه - چون سرور یه پوش شامل
    SessionId برمی‌گردونه، حتی اگه همین لحظه ساخته شده باشه)."""
    if contact.get("IsEntity"):
        return None

    username = contact["Username"]
    cached = contact_cache.get_session(username)
    if cached:
        return cached

    session_id = await page.evaluate(
        _SUB_USER_SESSION_JS,
        {"fromUsername": USERNAME, "username": username, "timeoutMs": DEFAULT_TIMEOUT_MS},
    )
    contact_cache.put_session(username, session_id)
    return session_id


async def _clear_conversation(page, contact: dict) -> dict:
    """بعد از ارسال موفق صدا زده می‌شه (اگه clear_after_send=True). عمداً هیچ
    Exception ای بیرون نمی‌ده - یه شکست تو پاک‌کردن تاریخچه نباید کل عملیات
    ارسال (که موفق بوده) رو fail شده حساب کنه؛ فقط تو نتیجه‌ی برگشتی گزارش
    می‌شه که خودِ caller (یا لاگ batch) ببینه."""
    try:
        session_id = await _resolve_session_id(page, contact)
        if session_id is None:
            return {"attempted": False, "reason": "entity - پاک‌کردن برای گروه/کانال پیاده نشده"}
        await page.evaluate(
            _CLEAR_HISTORY_JS,
            {"fromUsername": USERNAME, "sessionId": session_id, "timeoutMs": DEFAULT_TIMEOUT_MS},
        )
        return {"attempted": True, "ok": True}
    except Exception as e:
        return {"attempted": True, "ok": False, "error": str(e)}


async def resolve_id_via_browser(name: str, headless: bool = HEADLESS) -> dict:
    """فقط id رو برمی‌گردونه (بدون ارسال پیام) - اگه تو کش باشه، اصلاً مرورگر
    باز نمی‌شه"""
    cached = contact_cache.get(name)
    if cached:
        return {"Username": cached["username"], "Alias": cached["alias"], "IsEntity": cached["is_entity"],
                "IsDeactive": cached.get("is_deactive", False)}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser)
        try:
            contact = await _resolve_contact(page, name)
        except DeactivatedContactError:
            # resolve_id فقط اطلاع‌رسانیه (نه تصمیم به ارسال) - پس به‌جای پرتاب
            # خطا، خودِ id رو با پرچم IsDeactive برمی‌گردونیم
            cached = contact_cache.get(name)
            contact = {"Username": cached["username"], "Alias": cached["alias"],
                       "IsEntity": cached["is_entity"], "IsDeactive": True}
        await browser.close()
        return contact


def resolve_id(name: str, headless: bool = HEADLESS) -> dict:
    return asyncio.run(resolve_id_via_browser(name, headless=headless))


async def send_text_via_browser(to_id: str, text: str, is_entity: bool = False,
                                 clear_after_send: bool = True, headless: bool = HEADLESS) -> dict:
    """ارسال مستقیم - to_id باید دقیق (username شخص یا id گروه/کانال) باشه، بدون جستجو.
    is_entity=True بذار اگه to_id مال یه گروه/کاناله (نه یک شخص).
    clear_after_send: ببین docstring بالای فایل - پیش‌فرض True، مثل v1.

    ⚠️ اسم این تابع در نسخه‌ی یکپارچه‌شده‌ی Robot_Reward از send_message به
    send_text تغییر کرد (2026-09-15) - فقط تو این کپی، نه تو پروژه‌ی اصلی
    Payamresan_sender_ws - چون send_message برای تابع batch جدید (پایین‌تر،
    امضای مشترک با v1) لازم بود."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser)
        result = await page.evaluate(
            _SEND_TEXT_JS,
            {"fromUsername": USERNAME, "toUsername": to_id, "text": text,
             "isEntity": is_entity, "timeoutMs": DEFAULT_TIMEOUT_MS},
        )
        result["time"] = _now_str()
        if clear_after_send:
            result["cleared"] = await _clear_conversation(page, {"Username": to_id, "IsEntity": is_entity})
        await browser.close()
        return result


def send_text(to_id: str, text: str, is_entity: bool = False, clear_after_send: bool = True,
              headless: bool = HEADLESS) -> dict:
    return asyncio.run(send_text_via_browser(to_id, text, is_entity=is_entity,
                                              clear_after_send=clear_after_send, headless=headless))


async def send_message_by_name_via_browser(name: str, text: str, clear_after_send: bool = True,
                                            headless: bool = HEADLESS) -> dict:
    """وقتی username/id دقیق رو نداری - اول تو جدول محلی مخاطبین (contact_cache)
    نگاه می‌کنه، و فقط در نبودش تو کل دایرکتوری شرکت (شخص + گروه/کانال) سرچ
    می‌کنه و نتیجه رو برای دفعه‌های بعد ذخیره می‌کنه.
    clear_after_send: ببین docstring بالای فایل."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser)

        contact = await _resolve_contact(page, name)

        result = await page.evaluate(
            _SEND_TEXT_JS,
            {"fromUsername": USERNAME, "toUsername": contact["Username"], "text": text,
             "isEntity": contact["IsEntity"], "timeoutMs": DEFAULT_TIMEOUT_MS},
        )
        result["alias"] = contact["Alias"]
        result["time"] = _now_str()
        if clear_after_send:
            result["cleared"] = await _clear_conversation(page, contact)
        await browser.close()
        return result


def send_message_by_name(name: str, text: str, clear_after_send: bool = True, headless: bool = HEADLESS) -> dict:
    return asyncio.run(send_message_by_name_via_browser(name, text, clear_after_send=clear_after_send,
                                                         headless=headless))


async def send_image_via_browser(to_id: str, image_path: str, caption: str = "", is_entity: bool = False,
                                  clear_after_send: bool = True, headless: bool = HEADLESS) -> dict:
    """ارسال مستقیم عکس - to_id باید دقیق (username شخص یا id گروه/کانال) باشه، بدون جستجو"""
    with open(image_path, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode()
    file_name = os.path.basename(image_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser, need_upload_session=True)
        result = await page.evaluate(
            _SEND_IMAGE_JS,
            {
                "fromUsername": USERNAME, "toUsername": to_id, "caption": caption,
                "fileBase64": file_b64, "fileName": file_name, "isEntity": is_entity, "timeoutMs": 20000,
            },
        )
        result["time"] = _now_str()
        if clear_after_send:
            result["cleared"] = await _clear_conversation(page, {"Username": to_id, "IsEntity": is_entity})
        await browser.close()
        return result


def send_image(to_id: str, image_path: str, caption: str = "", is_entity: bool = False,
                clear_after_send: bool = True, headless: bool = HEADLESS) -> dict:
    return asyncio.run(send_image_via_browser(to_id, image_path, caption, is_entity=is_entity,
                                               clear_after_send=clear_after_send, headless=headless))


async def send_image_by_name_via_browser(name: str, image_path: str, caption: str = "",
                                          clear_after_send: bool = True, headless: bool = HEADLESS) -> dict:
    with open(image_path, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode()
    file_name = os.path.basename(image_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser, need_upload_session=True)

        contact = await _resolve_contact(page, name)

        result = await page.evaluate(
            _SEND_IMAGE_JS,
            {
                "fromUsername": USERNAME, "toUsername": contact["Username"], "caption": caption,
                "fileBase64": file_b64, "fileName": file_name, "isEntity": contact["IsEntity"], "timeoutMs": 20000,
            },
        )
        result["alias"] = contact["Alias"]
        result["time"] = _now_str()
        if clear_after_send:
            result["cleared"] = await _clear_conversation(page, contact)
        await browser.close()
        return result


def send_image_by_name(name: str, image_path: str, caption: str = "", clear_after_send: bool = True,
                        headless: bool = HEADLESS) -> dict:
    return asyncio.run(send_image_by_name_via_browser(name, image_path, caption,
                                                       clear_after_send=clear_after_send, headless=headless))


async def resolve_many_via_browser(names: list, headless: bool = HEADLESS) -> dict:
    """id چند اسم رو با هم، تو یک لاگین/Session واحد پیدا و کش می‌کنه (به‌جای
    این‌که برای هرکدوم جدا مرورگر باز کنه) - نتیجه: {name: contact_dict}"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser)
        results = {}
        for name in names:
            try:
                results[name] = await _resolve_contact(page, name)
            except DeactivatedContactError as e:
                results[name] = {"IsDeactive": True, "error": str(e)}
        await browser.close()
        return results


def resolve_many(names: list, headless: bool = HEADLESS) -> dict:
    return asyncio.run(resolve_many_via_browser(names, headless=headless))


_RUNLOG_COMPONENT = "sender.v2"


def _normalize_batch_result(i: int, target, result: dict) -> dict:
    """Maps this file's own (already mostly English/ok-shaped) result dict
    to the version-agnostic item shape core/runlog.py understands - see
    that module's docstring. `resume_key` is the list index (str) - this
    file's own long-standing identity scheme for a batch item."""
    normalized = {
        "ok": result.get("ok", False),
        "resume_key": str(i),
        "contact": result.get("target", target),
        "to": result.get("to"),
        "duration_sec": result.get("elapsed_sec"),
        "error": result.get("error"),
        "permanent_failure": result.get("permanent_failure", False),
        "known_contact": result.get("known_contact"),
    }
    if "cleared" in result:
        normalized["cleared"] = result["cleared"]
    return normalized


def _is_permanent_failure(exc: Exception) -> bool:
    """تشخیص خطای دائمی (که دوباره تلاش کردنش فایده نداره) از خطای موقتی
    (که ممکنه دفعه‌ی بعد موفق بشه، مثل timeout شبکه). NOT_PERMITTED یعنی
    سرور صریحاً گفته این ارسال هیچ‌وقت اجازه نداره (مخاطب غیرفعال، یا عدم
    دسترسی نوشتن تو یه کانال/گروه)."""
    return isinstance(exc, DeactivatedContactError) or "NOT_PERMITTED" in str(exc)


async def send_text_batch_via_browser(targets: list, message_fn, run_id: str = None,
                                       clear_after_send: bool = True, headless: bool = HEADLESS,
                                       on_result=None) -> list:
    """ارسال دسته‌ای واقعی - فقط یک‌بار لاگین/اتصال WebSocket، بعد همه‌ی
    پیام‌ها پشت‌سرهم رو همون Session زنده می‌ره (نه یک مرورگر جدا برای هرکدوم).
    targets: لیست اسم/id مقصدها (تکراری هم مجازه، برای تست فشار).
    message_fn(index, target) -> متن پیام برای اون مرحله.

    run_id/on_result (بازنویسی‌شده 1405/06/25 - ببین core/runlog.py): اگه
    run_id بدی، رزوم از core.runlog.resume_done_keys می‌آد (نه یه فایل
    مخصوص این فایل) - همون log_item که on_result صدا می‌زنه، خودش رکورد
    resume هم هست. اگه (مثلاً وسط ارسال به ۳۰۰۰ نفر) اسکریپت کرش کرد یا
    قطع شد، با اجرای دوباره‌ی همین run_id، کسایی که قبلاً موفق پیام گرفتن
    خودکار رد می‌شن. اگه run_id بدون on_result بدی، فقط resume فعاله بدون
    لاگ زنده (این تابع خودش core.runlog.log_item رو مستقیم صدا نمی‌زنه -
    فقط normalize می‌کنه و به on_result می‌ده؛ caller مسئول واقعاً لاگ‌کردنه).

    clear_after_send: ببین docstring بالای فایل - پیش‌فرض True، مثل v1.
    خروجی: لیست دیکشنری نتیجه به همراه زمان‌بندی هر ارسال."""
    done_indices = set()
    if run_id:
        done_indices = runlog.resume_done_keys(run_id, _RUNLOG_COMPONENT)
        if done_indices:
            print(f"[Resume] run_id={run_id}: {len(done_indices)} مورد قبلاً موفق ارسال شده بودن، رد می‌شن")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser)

        results = []
        for i, target in enumerate(targets):
            if str(i) in done_indices:
                result = {"ok": True, "index": i, "target": target, "skipped": True, "known_contact": None}
                results.append(result)
                if on_result:
                    on_result(_normalize_batch_result(i, target, result))
                continue

            text = message_fn(i, target)
            start = asyncio.get_event_loop().time()
            try:
                contact = await _resolve_contact(page, target)
                reply = await page.evaluate(
                    _SEND_TEXT_JS,
                    {"fromUsername": USERNAME, "toUsername": contact["Username"], "text": text,
                     "isEntity": contact["IsEntity"], "timeoutMs": DEFAULT_TIMEOUT_MS},
                )
                elapsed = asyncio.get_event_loop().time() - start
                result = {
                    "ok": True, "index": i, "target": target, "to": contact["Username"],
                    "elapsed_sec": round(elapsed, 3), "repoId": reply.get("repoId"), "time": _now_str(),
                    "known_contact": contact.get("FromCache"),
                }
                if clear_after_send:
                    result["cleared"] = await _clear_conversation(page, contact)
            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start
                permanent = _is_permanent_failure(e)
                if permanent and not isinstance(e, DeactivatedContactError):
                    # NOT_PERMITTED از خودِ سرور اومد (نه از کش) - یعنی تازه
                    # فهمیدیم؛ تو کش هم ثبتش کن تا دیگه هیچ‌وقت تلاش نشه
                    contact_cache.mark_deactive(target)
                result = {
                    "ok": False, "index": i, "target": target, "time": _now_str(),
                    "elapsed_sec": round(elapsed, 3), "error": str(e), "permanent_failure": permanent,
                }

            results.append(result)
            if on_result:
                on_result(_normalize_batch_result(i, target, result))

        await browser.close()
        return results


def send_text_batch(targets: list, message_fn, run_id: str = None, clear_after_send: bool = True,
                     headless: bool = HEADLESS, on_result=None) -> list:
    return asyncio.run(send_text_batch_via_browser(targets, message_fn, run_id=run_id,
                                                    clear_after_send=clear_after_send, headless=headless,
                                                    on_result=on_result))


async def send_image_batch_via_browser(targets: list, image_path: str, caption_fn, run_id: str = None,
                                        clear_after_send: bool = True, headless: bool = HEADLESS,
                                        on_result=None) -> list:
    """مثل send_text_batch ولی برای عکس - یک‌بار فایل رو از دیسک می‌خونه و
    base64 می‌کنه، بعد تو همون یک Session (یک لاگین) برای هر مقصد دوباره
    آپلودش می‌کنه (هر پیام تصویری باید جدا آپلود بشه، این بخشِ پروتکله؛
    فقط لاگین/اتصاله که مشترکه) و می‌فرسته. run_id/on_result/clear_after_send:
    ببین توضیح send_text_batch"""
    with open(image_path, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode()
    file_name = os.path.basename(image_path)

    done_indices = set()
    if run_id:
        done_indices = runlog.resume_done_keys(run_id, _RUNLOG_COMPONENT)
        if done_indices:
            print(f"[Resume] run_id={run_id}: {len(done_indices)} مورد قبلاً موفق ارسال شده بودن، رد می‌شن")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser, need_upload_session=True)

        results = []
        for i, target in enumerate(targets):
            if str(i) in done_indices:
                result = {"ok": True, "index": i, "target": target, "skipped": True, "known_contact": None}
                results.append(result)
                if on_result:
                    on_result(_normalize_batch_result(i, target, result))
                continue

            caption = caption_fn(i, target)
            start = asyncio.get_event_loop().time()
            try:
                contact = await _resolve_contact(page, target)
                reply = await page.evaluate(
                    _SEND_IMAGE_JS,
                    {
                        "fromUsername": USERNAME, "toUsername": contact["Username"], "caption": caption,
                        "fileBase64": file_b64, "fileName": file_name, "isEntity": contact["IsEntity"],
                        "timeoutMs": 25000,
                    },
                )
                elapsed = asyncio.get_event_loop().time() - start
                result = {
                    "ok": True, "index": i, "target": target, "to": contact["Username"],
                    "elapsed_sec": round(elapsed, 3), "repoId": reply.get("repoId"), "time": _now_str(),
                    "known_contact": contact.get("FromCache"),
                }
                if clear_after_send:
                    result["cleared"] = await _clear_conversation(page, contact)
            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start
                permanent = _is_permanent_failure(e)
                if permanent and not isinstance(e, DeactivatedContactError):
                    contact_cache.mark_deactive(target)
                result = {
                    "ok": False, "index": i, "target": target, "permanent_failure": permanent, "time": _now_str(),
                    "elapsed_sec": round(elapsed, 3), "error": str(e),
                }

            results.append(result)
            if on_result:
                on_result(_normalize_batch_result(i, target, result))

        await browser.close()
        return results


def send_image_batch(targets: list, image_path: str, caption_fn, run_id: str = None,
                      clear_after_send: bool = True, headless: bool = HEADLESS, on_result=None) -> list:
    return asyncio.run(send_image_batch_via_browser(targets, image_path, caption_fn, run_id=run_id,
                                                     clear_after_send=clear_after_send, headless=headless,
                                                     on_result=on_result))


# ─── امضای مشترک با v1 - نقطه‌ی اتصال واقعی به Senders/payamresan.py ────────────
async def _resolve_contact_for_rendered_item(page, item: dict) -> dict:
    """اگه آیتم `chat_user_id` داشته باشه (از یه دفترچه‌ی مخاطبین آینده -
    ببین payamresan.py._resolve_chat_user_id، هنوز پیاده نشده)، مستقیم همون
    رو به‌عنوان id مقصد قبول می‌کنیم - بدون سرچ، بدون _resolve_contact، بدون
    لمس contact_cache (چون از قبل شناخته‌شده‌ست). فرض می‌کنیم شخصه نه
    گروه/کانال - چون chat_user_id از یه دایرکتوری مبتنی بر panel_user_id
    (هویت یک شخص) میاد، نه یه گروه/کانال.

    وگرنه (رفتار فعلی/همیشگی) با `contact` (اسم) از مسیر سرچ+کش معمولی
    (_resolve_contact) عبور می‌کنیم."""
    chat_user_id = item.get("chat_user_id")
    if chat_user_id:
        return {"Username": chat_user_id, "Alias": item.get("contact", chat_user_id), "IsEntity": False,
                "FromCache": True}
    return await _resolve_contact(page, item["contact"])


async def send_message_via_browser(rendered: list, agents_csv_path: str = "", num_tabs: int = 1,
                                    clear_after_send: bool = True, run_id: str = None,
                                    headless: bool = HEADLESS, on_result=None) -> list:
    """امضای مشترک با v1 (send_message.py) - این چیزی‌ست که Senders/payamresan.py
    واقعاً صدا می‌زند، ببین docstring بالای فایل. rendered مخلوطه (بعضی
    پیام‌ها متن‌خالص، بعضی عکس‌دار)، همه تو یک لاگین/session واحد، یکی‌یکی
    پردازش می‌شن - چون این معماری (برخلاف v1 که open_chat واقعاً هزینه‌بر
    بود) هیچ فایده‌ای از گروه‌بندی/چندتب نمی‌بره؛ هر پیام یه فریم WS ارزونه.

    agents_csv_path: نادیده گرفته می‌شه (دقیقاً دلیل v1 - هماهنگی امضا).
    num_tabs: نادیده گرفته می‌شه (معماری ذاتاً سریاله).
    run_id/on_result (بازنویسی‌شده 1405/06/25 - ببین core/runlog.py): مثل
    send_text_batch - رزوم از core.runlog.resume_done_keys می‌آد، on_result
    هر نتیجه‌ی normalize‌شده رو به caller می‌ده (Senders/payamresan.py که
    از سمت Senders/sender_thread.py دریافتش کرده، مستقیم به
    core.runlog.log_item وصلش می‌کنه)."""
    done_indices = set()
    if run_id:
        done_indices = runlog.resume_done_keys(run_id, _RUNLOG_COMPONENT)
        if done_indices:
            print(f"[Resume] run_id={run_id}: {len(done_indices)} مورد قبلاً موفق ارسال شده بودن، رد می‌شن")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        context, page = await _open_session(browser, need_upload_session=True)

        results = []
        for i, item in enumerate(rendered):
            if str(i) in done_indices:
                result = {"ok": True, "index": i, "target": item.get("contact"), "skipped": True,
                           "known_contact": None}
                results.append(result)
                if on_result:
                    on_result(_normalize_batch_result(i, item.get("contact"), result))
                continue

            start = asyncio.get_event_loop().time()
            try:
                contact = await _resolve_contact_for_rendered_item(page, item)
                image = item.get("image")
                caption = item.get("caption") or ""
                if image:
                    with open(image, "rb") as f:
                        file_b64 = base64.b64encode(f.read()).decode()
                    js = _SEND_IMAGE_JS if _is_image_path(image) else _SEND_FILE_JS
                    reply = await page.evaluate(
                        js,
                        {"fromUsername": USERNAME, "toUsername": contact["Username"], "caption": caption,
                         "fileBase64": file_b64, "fileName": os.path.basename(image),
                         "isEntity": contact["IsEntity"], "timeoutMs": 25000},
                    )
                else:
                    reply = await page.evaluate(
                        _SEND_TEXT_JS,
                        {"fromUsername": USERNAME, "toUsername": contact["Username"], "text": caption,
                         "isEntity": contact["IsEntity"], "timeoutMs": DEFAULT_TIMEOUT_MS},
                    )
                elapsed = asyncio.get_event_loop().time() - start
                result = {
                    "ok": True, "index": i, "target": item.get("contact"), "to": contact["Username"],
                    "elapsed_sec": round(elapsed, 3), "repoId": reply.get("repoId"), "time": _now_str(),
                    "known_contact": contact.get("FromCache"),
                }
                if clear_after_send:
                    result["cleared"] = await _clear_conversation(page, contact)
            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start
                permanent = _is_permanent_failure(e)
                if permanent and not isinstance(e, DeactivatedContactError):
                    contact_cache.mark_deactive(item.get("contact"))
                result = {
                    "ok": False, "index": i, "target": item.get("contact"), "time": _now_str(),
                    "elapsed_sec": round(elapsed, 3), "error": str(e), "permanent_failure": permanent,
                }

            results.append(result)
            if on_result:
                on_result(_normalize_batch_result(i, item.get("contact"), result))

        await browser.close()
        return results


def send_message(rendered: list, agents_csv_path: str = "", num_tabs: int = 1,
                  clear_after_send: bool = True, run_id: str = None, headless: bool = HEADLESS,
                  on_result=None) -> list:
    """قرارداد Senders/payamresan.py: send_message(rendered, agents_csv_path, num_tabs, clear_after_send, run_id, on_result).
    rendered: [{"contact", "image", "caption", "panel_user_id"?, "chat_user_id"?}, ...]"""
    if not rendered:
        return []
    return asyncio.run(send_message_via_browser(rendered, agents_csv_path=agents_csv_path, num_tabs=num_tabs,
                                                 clear_after_send=clear_after_send, run_id=run_id,
                                                 headless=headless, on_result=on_result))


if __name__ == "__main__":
    # سناریو ۱: ارسال مستقیم با id دقیق (بدون جستجو) - چه شخص چه گروه/کانال
    result = send_text("analiz.gozareshat", "تست سناریو ۱ - ارسال مستقیم با username")
    print("DIRECT SENT OK:", json.dumps(result, ensure_ascii=False))

    # سناریو ۲: ارسال با جستجوی اسم در کل دایرکتوری شرکت (شخص یا گروه/کانال)
    result2 = send_message_by_name("گروه آنالیز و گزارشات", "تست سناریو ۲ - ارسال با جستجوی نام گروه")
    print("SEARCH SENT OK:", json.dumps(result2, ensure_ascii=False))
