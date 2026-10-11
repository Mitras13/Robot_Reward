---
description: Git workflow conventions for this project - staging, committing, pushing.
applies_to: "*"
---

# قرارداد Git

- هیچ‌وقت commit نکن مگر کاربر صریحاً بخواهد. هیچ‌وقت push نکن مگر کاربر
  صریحاً همان push را تایید کرده باشد.
- برای stage کردن، هیچ‌وقت `git add -A` یا `git add .` استفاده نکن - همیشه
  فایل‌ها را با اسم صریح اضافه کن، بعد `git status` را برای بازبینی نهایی
  چک کن.
- `.claude/` معمولاً از commit کنار گذاشته می‌شود (state موقت/session)،
  **به‌جز** بخش‌های عمدی و پایدار پروژه (`.claude/rules/`,
  `.claude/skills/`, `.claude/commands/`, `.claude/settings.json`) که
  جزو استاندارد رسمی پروژه‌اند و باید commit شوند. فایل‌های شخصی/session
  (`settings.local.json`, `*.lock`, `active-task.json`, پلن‌ها) هیچ‌وقت
  commit نمی‌شوند.
- قبل از هر add، اگر فایلی مشکوک به حاوی بودن secret به نظر می‌رسد (حتی با
  اسم بی‌ضرر)، محتوایش را چک کن؛ و با `git check-ignore -v` مطمئن شو
  `.env`/`*token*`/`*credentials*`/`contacts_cache.json` هنوز gitignore
  هستند.
- پیام کامیت باید با خط attribution که در سیستم‌ریمایندر همان لحظه داده
  شده تمام شود (نه یک خط ثابت حفظ‌شده از قبل - این می‌تواند بین session‌ها
  عوض شود).
- ترجیح با commit جدید است، نه `--amend`؛ هیچ‌وقت از عملیات مخرب
  (`push --force`, `reset --hard`, `clean -f`, حذف برنچ) بدون درخواست صریح
  کاربر استفاده نکن.

مرتبط: [[scope-boundaries]]
