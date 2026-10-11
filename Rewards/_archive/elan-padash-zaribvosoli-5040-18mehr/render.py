"""
elan-padash-zaribvosoli-5040-18mehr/render.py

Same text to every recipient - wording supplied by the user 2026-10-10, made
warmer on request (same facts/tiers), text only.
"""

from Senders.message import OutboundMessage

TEXT = """سلام همکار عزیز ۵۰۴۰ 🌸

یه خبر خوب داریم! 😍
🏆 رقابت افزایش ضریب وصولی کارشناسان ۵۰۴۰ از امروز شروع شد!

📅 بازه رقابت: از ۱۸ مهر تا پایان ۳۰ مهر

💡 رتبه‌ی هر کارشناس بر اساس ضریب وصولیش مشخص می‌شه.

🎁 پله‌های افزایش پورسانت:
🥇 رتبه ۱ تا ۱۰ ➜ ۱۰۰٪ افزایش پورسانت (یعنی دو برابر!)
🥈 رتبه ۱۱ تا ۳۰ ➜ ۵۰٪ افزایش پورسانت
🥉 رتبه ۳۱ تا ۵۰ ➜ ۲۰٪ افزایش پورسانت
🏅 رتبه ۵۱ تا ۱۰۰ ➜ ۱۰٪ افزایش پورسانت
⭐ رتبه ۱۰۱ تا ۲۰۰ ➜ ۸٪ افزایش پورسانت
⭐ رتبه ۲۰۱ تا ۳۵۰ ➜ ۶٪ افزایش پورسانت
⭐ رتبه ۳۵۱ تا ۵۵۰ ➜ ۵٪ افزایش پورسانت

✨ ۵۵۰ نفر پاداش می‌گیرن، پس شانس تو هم خیلی زیاده!
🔥 ضریب وصولی بالاتر = رتبه بهتر = پورسانت بیشتر

💪 تا آخر مهر وقت داری خودت رو به پله‌های بالاتر برسونی!

منتظر دیدن اسمت بین نفرات برتر هستیم 🚀💰
موفق باشی ❤️"""


def render(report, reward_id, slot):
    return [
        OutboundMessage(reward_id=reward_id, slot=slot, panel_user_id=name,
                        chat_user_id="", contact=name, text=TEXT)
        for name in report["recipients"]
    ]
