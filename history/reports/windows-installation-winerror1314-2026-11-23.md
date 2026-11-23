# توقف نصب Windows هنگام آماده‌سازی cache مدل — ۲۳ نوامبر۲۰۲۶، تهران

## شاهد دریافتی و وضعیت

کاربر خروجی واقعی restore_environment_windows.bat را فرستاد. دانلود Qwen/Qwen2.5-7B-Instruct با revision ثابت a09a35458c702b33eeacc393d103063234e8bc28 آغاز شده بود. هشدار نبود hf_xet، fallback به HTTP را اعلام کرد و پس از آن دانلود ادامه یافت. progress هر چهار shard وزن‌ها به۱۰۰٪ رسید (اندازه‌های گرد‌شدهٔ نمایشی۳٫۹۵،۳٫۸۶،۳٫۸۶ و۳٫۵۶GB؛ حدود۱۷تا۱۹٫۵دقیقه). این نمایش، بررسی کامل فایل‌ها یا checksum روی ماشین کاربر نیست.

خطای نهایی در ساخت پیوند config.json از blobs به snapshots بود:

`OSError: [WinError 1314] A required privilege is not held by the client`

مسیر مقصد در cache همان کاربر:
`C:\Users\pc\.cache\huggingface\hub\models--Qwen--Qwen2.5-7B-Instruct\snapshots\a09a35458c702b33eeacc393d103063234e8bc28\config.json`

فرمان کمکی --prepare-models با exit status1 پایان یافت؛ برنامهٔ اصلی CalledProcessError ثبت کرد و پیام Setup did not complete / no experiment was started نشان داد. فایل گزارش تلاش طبق لاگ recovery_logs/restore-1795423858312287600.json است؛ محتوای خود فایل هنوز دریافت نشده است. نصب کامل و READY تأیید نشده، اجرای سؤال‌های پروژه نیز گزارش نشده است. این مورد شکست واقعی راه‌اندازی است، نه نتیجهٔ معنایی پژوهش.

## تشخیص و بررسی

WinError1314 به نداشتن امتیاز لازم برای ساخت symbolic link مربوط است. هشدار hf_xet علت توقف نیست: دانلود با HTTP ادامه یافته بود. متغیر HF_HUB_DISABLE_SYMLINKS_WARNING موجود در نصاب فقط هشدار را مخفی می‌کند؛ مجوز ساخت پیوند نمی‌دهد و آن را غیرفعال نمی‌کند. علت دقیق اینکه تشخیص خودکار/مسیر fallback کتابخانه در این اجرا از خطا جلوگیری نکرده، بدون نسخهٔ نصب‌شده و بررسی همان ماشین قطعی نشده است.

کد رسمی huggingface_hub و راهنمای cache نسخهٔ۰٫۳۶٫۲ از GitHub دریافت و خوانده شدند. این راهنما برای symbolic link در Windows فعال‌بودن Developer Mode یا اجرای Python با دسترسی administrator را توضیح می‌دهد. نسخهٔ دقیق کتابخانه در ماشین کاربر از این لاگ معلوم نیست؛ نسخهٔ منبع بررسی‌شده نباید به‌عنوان نسخهٔ نصب‌شده معرفی شود.

منابع بررسی‌شده:
- https://raw.githubusercontent.com/huggingface/huggingface_hub/v0.36.2/src/huggingface_hub/file_download.py
- https://raw.githubusercontent.com/huggingface/huggingface_hub/v0.36.2/docs/source/en/guides/manage-cache.md

## راهنمای ادامه و حدود تأیید

اقدام پیشنهادی: پنجرهٔ نصب شکست‌خورده بسته شود، همان restore_environment_windows.bat در همان پوشه با Run as administrator و همان حساب pc اجرا شود. cache و .venv_hotpotqa پاک نشوند. استفاده از حساب دیگر یا مسیر cache تازه می‌تواند مانع استفاده از فایل‌های دانلودشده شود. فایل‌های کامل موجود معمولاً دوباره دانلود نمی‌شوند؛ تکمیل فایل‌های ناقص و دریافت مدل BGE ممکن است هنوز لازم باشد. هیچ تضمینی دربارهٔ کامل‌بودن cache کاربر داده نشد.

راه جایگزین مستند در صورت نیاز، فعال‌سازی Developer Mode و اجرای مجدد معمولی است. hf_xet برای رفع این خطای مجوز الزامی نیست. تا READY، نصب کامل تلقی نشود و اجرای توسعه آغاز نشود. این راهکار هنوز توسط کاربر اجرا/تأیید نشده؛ وضعیت مسئله باز است. هیچ کد پایپ‌لاین، پرامپت، فایل نصب یا داده تغییر نکرد و بستهٔ حذف‌شدهٔ بازیابی دوباره منتشر نشد.
