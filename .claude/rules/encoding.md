---
description: Persian/English language split and text-encoding conventions across the project.
applies_to: "*"
---

# قرارداد زبان و انکدینگ

## زبان

- **لاگ‌ها و کنسول: انگلیسی.** `conhost`/cmd نمی‌تواند فارسی RTL را همراه با
  متن انگلیسی به‌طور قابل‌اعتماد نمایش دهد - قبلاً باعث خرابی واقعی نمایش شده
  (`core/logging_setup.py`). هیچ متن فارسی داخل `logger.info(...)`/`print`
  کنسولی اضافه نکن.
- **فارسی فقط جایی که واقعاً محتوای کاربر/پیام است**: صفحات UI (`ui/`)، متن
  پیام‌های ارسالی (`render.py`ها)، و مقادیر نمایشی داخل `config/rewards.csv`
  (نام/شرکت/سطح).

## انکدینگ فایل‌های config/

هر فایل باید با همان encoding نوشته شود که خوانندهٔ آن فایل با آن باز
می‌کند - این دو تا الان دو قرارداد متفاوت دارند و اشتباه گرفتنشان یک باگ
واقعی همین پروژه بوده (نوشتن BOM روی `sender_version.txt` باعث شد
`payamresan.current_sender_version()` همیشه مقدار را غلط تشخیص بدهد):

- `config/rewards.csv` → `utf-8-sig` (BOM دارد) - چون
  `tick.load_rewards()` با `encoding="utf-8-sig"` می‌خوانَدش.
- `config/sender_version.txt` → `utf-8` **بدون BOM** - چون
  `Senders/payamresan.current_sender_version()` با `encoding="utf-8"`
  می‌خوانَدش و BOM باعث می‌شود مقدار هیچ‌وقت با `"1"`/`"2"` برابر نشود.

قبل از نوشتن اتمیک روی هر فایل config جدید، اول چک کن خواننده‌اش دقیقاً با
چه encoding باز می‌شود (`ui/services/config_store.py._atomic_write_text`
همین الگو را دارد و پارامتر `encoding` می‌گیرد - از همان استفاده کن، آن را
دوباره پیاده نکن).
