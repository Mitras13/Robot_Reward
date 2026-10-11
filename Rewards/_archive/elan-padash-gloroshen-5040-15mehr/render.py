"""
elan-padash-gloroshen-5040-15mehr/render.py

Same text to every recipient - user-approved wording 2026-10-07, text only
(no poster, user decision).
"""

from Senders.message import OutboundMessage

TEXT = """همکاران عزیز فروش ۵۰۴۰ 🌸

✨ پاداش ویژه «ضد لک گلورشن» از امروز شروع شد!

📅 بازه اجرای طرح: ۱۵ مهر ساعت ۰۰:۰۰ تا ۱۰ آبان ساعت ۲۳:۵۹
🎯 ملاک پرداخت: تعداد فاکتورهای وصولی کارتابلی پک ضد لک گلورشن در بازه طرح (فقط تاریخ وصول ملاکه)

🏆 پاداش نفرات برتر:
🥇 نفر اول: ۳,۰۰۰,۰۰۰ تومان
🥈 نفرات دوم و سوم: ۲,۵۰۰,۰۰۰ تومان (هر نفر)
🥉 نفرات چهارم تا هفتم: ۲,۰۰۰,۰۰۰ تومان (هر نفر)
🏅 نفرات هشتم تا دوازدهم: ۱,۰۰۰,۰۰۰ تومان (هر نفر)
🏅 نفرات سیزدهم تا هفدهم: ۷۵۰,۰۰۰ تومان (هر نفر)
🏅 نفرات هجدهم تا سی‌ام: ۵۰۰,۰۰۰ تومان (هر نفر)
🏅 نفرات سی‌ویکم تا چهلم: ۳۰۰,۰۰۰ تومان (هر نفر)

💪 از همین امروز با تمرکز روی فروش این محصول، همه‌ی تلاشتون رو بکنید تا به پاداش برسید.
📩 هر زمان شامل پاداش بشید، پیام پاداش و جایگاهتون رو براتون ارسال می‌کنیم.

موفق باشید ❤️"""


def render(report, reward_id, slot):
    return [
        OutboundMessage(reward_id=reward_id, slot=slot, panel_user_id=name,
                        chat_user_id="", contact=name, text=TEXT)
        for name in report["recipients"]
    ]
