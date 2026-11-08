# پنج پایلوت مستقل از max4 اصلی — تحویل ۲۰۲۶-۱۱-۰۸

درخواست کاربر ساخت پنج آزمایش مستقل بود؛ هر پنج پوشه مستقیماً از ZIP پذیرفته‌شده v3.2.4-max4 استخراج شدند. هیچ‌کدام ادامه نسخه دیگر نیست. اصلاحات role_identity/target_phrase/explicit_target پیشین به این بسته‌ها منتقل نشدند.

SHA256 مبنا: `ad77a0d34992910d089f13fa30efee27040132bc3a93e6c8d868a10ef5a0a62b`.
بسته‌های نهایی با خود ZIP اصلی مقایسه شدند: مدل/revision/config، نمونه‌ها، دو پرامپت ثابت و سایر فایل‌های اصلی Python خارج از فهرست مجاز برابر بودند. مشخصات هر فایل و diff کد به تفکیک کنار این گزارش ثبت است.

| نسخه | تغییر | تست آفلاین موفق |
|---|---|---|
| 01 structure_messages | پیام اسلات/dependency دقیق؛ راهنمای ادغام همان موجودیت در سقف۴؛ معیار اعتبار ثابت | 131 |
| 02 relation_diagnostics | جهت دوطرفه، مکان/زمان تأسیس، هویت/تولید؛ فقط گزارش | 138 |
| 03 target_patch | استخراج دسته + دو حالت مستقل استخراج‌تنها/پچ محدود ریشه | 138 |
| 04 constraint_diagnostics | عنوان اثر، اتصال قیود به هر شخص، فرد مفرد مستثنا؛ فقط گزارش | 138 |
| 05 decomposition_diagnostics | مصرف ظاهری اسلات، بازپرسش هویت، تک‌گرهی نیازمند بررسی؛ فقط گزارش | 134 |

هر نسخه شامل ۱۲۴ تست اصلی است؛ در نسخه۱ تنها سه assertion برابری پیام قدیمی سقف گره به بررسی prefix تبدیل شد؛ تست‌ها حذف/skip نشدند. شمارش بالا مجموع اجرای suite هر نسخه است، نه تعداد تست‌های مستقل منحصربه‌فرد در کل پروژه.

## دامنه و شواهد بازپخش

برای هر پنج نسخه، همان ۴۷ تلاش ساختاری و ۳۷ تصمیم داوری ذخیره‌شده مبنا بدون فراخوانی مدل بازپخش شد. تصمیم ساختاری و خود planها در بازپخش برابر مبنا هستند؛ این نتیجه، تولید واقعی نسخه جدید نیست.

- نسخه۱: متن خطای قبلی در ۲،۱۵،۱۸،۳۲ تغییر می‌کند؛ پرامپت تلاش اول تمام۴۰ ثابت است. خطا در تلاش دوم به مدل می‌رسد. گراف خودکار اصلاح نمی‌شود.
- نسخه۲: ۱۳،۱۴،۲۵ مشکوک؛۳۷unknown. جابه‌جایی طرفین همراه با وارونگی درست جهت پذیرفته می‌شود. پرامپت‌ها، trace و داوری بازپخش دقیقاً برابر مبنا؛ گزارش‌های تازه صفر فراخوانی دارند.
- نسخه۳: الگوی محدود type/kind/sort of noun برای other؛ فقط راهنمای۲۵ و۳۳ و metadata هدف آن‌ها تغییر می‌کند. form در پیاده‌سازی نهایی اضافه نشده است. سایر قواعد گسترده explicit_target قدیمی وارد نشده‌اند. استخراج دسته، رد قطعی ریشه اشتباه۳۳ ایجاد نمی‌کند.
- نسخه۳: روی خروجی‌های مبنا،۱۹،۳۶،۴۰ واجد یک فرصت پچ‌اند. پچ فقط question/answer_type ریشه است؛ IDs/dependencies/leaves ثابت، مجموع تولید حداکثر۲. بعد از تلاش دوم ساختاری فرصت سوم وجود ندارد. علاوه بر اعتبار ساختاری/root_check، حفظ واژگان محتوایی قبلی و صراحت هدف در نوع و سؤال لازم است؛ other برای دورزدن خطا کافی نیست. raw proposal/پیام/دلیل در trace نگه داشته می‌شود. رد پچ، درخت قبلی و خطای هدف را حفظ می‌کند. این روش با بازتولید کل درختِ آزمایش‌های ناموفق قبلی متفاوت است. کنترل لغوی اثبات حفظ همه روابط یا قیود نیست و می‌تواند بازنویسی معنایی درست را هم رد کند.
- نسخه۴:۱۹،۲۴،۳۷مشکوک؛۳۴unknown؛۳موردno_violation_found در دامنه محدود. خطای۳۷ تبدیل فرد مفرد به گروه است؛ تکرار واژه استثنا در برگ جاری فرض نشده. alias/پارافریز و امکان پاسخ منفی با رد یک جزء، محدودیت‌های گزارش‌اند.
- نسخه۵:۱۸،۲۴،۲۸ به‌دلیل تکرار پس از حذف اسلات مشکوک؛۳۷unknown. تک‌گرهی۳،۹،۲۶ با توضیح نیاز به بررسی انسانی unknown هستند؛ نه خودکار نادرست و نه خودکار درست. هیچ حداقل۲گره‌ای وجود ندارد.

در نسخه‌های۲/۴/۵، گزارش summary کامل بازسازی‌شده از خروجی قدیمی برابر مبناست؛ diagnostics و max4_comparison در ZIP گزارش اضافه‌اند. شکل درخت یا رأی داور با این تشخیص‌ها تغییر نمی‌کند. اتصال به رد/تعمیر کار بعدی و نیازمند ارزیابی است.

## اجرای کنترل‌شده

هر ZIP در پوشه تازه؛ همان محیط و مدل قبلی؛ `run_decomposition_test.bat` برای هر نسخه. نسخه۳ ابتدا `run_extraction_only.bat` و سپس BAT اصلی اجرا شود: `_extract` و `_repair` خروجی/checkpoint جدا دارند. direct Python پیش‌فرض استخراج است، BAT اصلی `--target-repair` می‌فرستد. تغییر حالت روی checkpoint موجود مسدود می‌شود. نسخه۳ نسبت به مبنا دو تغییر دارد؛ مقایسه extraction-only با repair اثر افزوده پچ را جدا می‌کند.

همه بسته‌ها `max4_comparison.json/md` می‌سازند که نتیجه جدید را با مرجع ثبت‌شده max4 (۳۷معتبر،۳نامعتبر،۸۰فراخوانی،۴۷٬۹۴۴توکن) به تفکیک سؤال مقایسه می‌کند. مرجع از gold استفاده نمی‌کند و وارد پرامپت نمی‌شود. نسخه‌های تشخیصی `diagnostics.json/md` و گزارش ازپیش‌محاسبه‌شده روی خروجی قدیمی در evaluation دارند. تنظیمات/هش کد، مسیر خروجی و mode از اختلاط checkpoint جلوگیری می‌کند.

آزمون پچ شامل رد JSON/اسلات/حذف قید/نوع مبهم، حفظ درخت اولیه، سقف۲، عدم مصرف دوباره در resume، ثبت raw و هزینه واقعی شامل judge و جداسازی mode است. آزمون‌های تشخیصی مثبت/منفی/abstain و حضور گزارش در ZIP را بررسی می‌کنند. ZIPها دوباره استخراج شدند، manifest تک‌تک فایل‌ها و code_digest بررسی شد و --help بدون بارگیری مدل اجرا شد. BAT در Windows بومی اجرا نشده؛ launcherهای تغییرکرده CRLF دارند. نتیجه Qwen واقعی جدید و full RAG اجرا نشده؛ موفقیت معنایی اعلام نمی‌شود. مبنای پذیرفته‌شده همچنان max4 اصلی است.

## تحویل روی صفحه اصلی مخزن

شاخه پیش‌فرض از remote HEAD بررسی شد: `downloads/operadic-decomposition-v0.2.0`.
commit تحویل: `eb304676fb44c17ddcb64be217b652a1540f7276`.
پنج ZIP و پنج TXT جدا در ریشه هستند؛ هر ده URL ثابت دانلود و با SHA256/اندازه محلی مقایسه شدند.

### max4_01_structure_messages_v1

- [hotpotqa_max4_01_structure_messages_v1.zip](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_01_structure_messages_v1.zip) — SHA256 `46ad0be04b64d20e6193836a054baaff207027f66e19e022d980fa2c104705b7`؛ 282759 bytes؛ دانلود تأیید شد.
- [hotpotqa_max4_01_structure_messages_v1.txt](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_01_structure_messages_v1.txt) — SHA256 `11bdec4204df07950713b4000e0fdea13cc70626d593755dcf01efb9c637c9e8`؛ 4795 bytes؛ دانلود تأیید شد.
- [پیش‌آزمون](max4_01_structure_messages_v1-preflight.json)، [diff مستقل](max4_01_structure_messages_v1-source.diff)، [تست‌ها](max4_01_structure_messages_v1-tests.txt)، [manifest فایل‌ها](max4_01_structure_messages_v1-source-manifest.json).

### max4_02_relation_diagnostics_v1

- [hotpotqa_max4_02_relation_diagnostics_v1.zip](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_02_relation_diagnostics_v1.zip) — SHA256 `5bce0463891a5a137dff2a7b4f81d5a37bcf67b0e58e9950baa5d2b6d39d5c5c`؛ 295749 bytes؛ دانلود تأیید شد.
- [hotpotqa_max4_02_relation_diagnostics_v1.txt](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_02_relation_diagnostics_v1.txt) — SHA256 `a54e0d4629d808de1ae7b9a5ab8003ccbd35e528ad212a44175243a1f129b342`؛ 5029 bytes؛ دانلود تأیید شد.
- [پیش‌آزمون](max4_02_relation_diagnostics_v1-preflight.json)، [diff مستقل](max4_02_relation_diagnostics_v1-source.diff)، [تست‌ها](max4_02_relation_diagnostics_v1-tests.txt)، [manifest فایل‌ها](max4_02_relation_diagnostics_v1-source-manifest.json).

### max4_03_target_patch_v1

- [hotpotqa_max4_03_target_patch_v1.zip](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_03_target_patch_v1.zip) — SHA256 `19235fcfe9616fc5606d9d58a57f589224776d2a36f47293e4b0343b2e574437`؛ 287762 bytes؛ دانلود تأیید شد.
- [hotpotqa_max4_03_target_patch_v1.txt](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_03_target_patch_v1.txt) — SHA256 `64d9eb7cc32954e7e3d0c03316d49110510408aa70634354dcf7dcbe57f390b1`؛ 6768 bytes؛ دانلود تأیید شد.
- [پیش‌آزمون](max4_03_target_patch_v1-preflight.json)، [diff مستقل](max4_03_target_patch_v1-source.diff)، [تست‌ها](max4_03_target_patch_v1-tests.txt)، [manifest فایل‌ها](max4_03_target_patch_v1-source-manifest.json).

### max4_04_constraint_diagnostics_v1

- [hotpotqa_max4_04_constraint_diagnostics_v1.zip](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_04_constraint_diagnostics_v1.zip) — SHA256 `a40c6b805f7ac23b516c35270742e61b5843944c07225bd7b680c18ccc02a3b5`؛ 296885 bytes؛ دانلود تأیید شد.
- [hotpotqa_max4_04_constraint_diagnostics_v1.txt](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_04_constraint_diagnostics_v1.txt) — SHA256 `00fc7e662b989bf21425242717e59f11aad908bb9bd76b6c703586db205c10f7`؛ 5176 bytes؛ دانلود تأیید شد.
- [پیش‌آزمون](max4_04_constraint_diagnostics_v1-preflight.json)، [diff مستقل](max4_04_constraint_diagnostics_v1-source.diff)، [تست‌ها](max4_04_constraint_diagnostics_v1-tests.txt)، [manifest فایل‌ها](max4_04_constraint_diagnostics_v1-source-manifest.json).

### max4_05_decomposition_diagnostics_v1

- [hotpotqa_max4_05_decomposition_diagnostics_v1.zip](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_05_decomposition_diagnostics_v1.zip) — SHA256 `48e0623daa91901bbca539131a32a95e4ca29470d136f1c5353a3d97e6d42c87`؛ 295762 bytes؛ دانلود تأیید شد.
- [hotpotqa_max4_05_decomposition_diagnostics_v1.txt](https://raw.githubusercontent.com/omidghpython/VIE/eb304676fb44c17ddcb64be217b652a1540f7276/hotpotqa_max4_05_decomposition_diagnostics_v1.txt) — SHA256 `d211610fbe920aa7e3518e072f5db04ce6d94b571c3edf887f9cd76438dc7b9f`؛ 5158 bytes؛ دانلود تأیید شد.
- [پیش‌آزمون](max4_05_decomposition_diagnostics_v1-preflight.json)، [diff مستقل](max4_05_decomposition_diagnostics_v1-source.diff)، [تست‌ها](max4_05_decomposition_diagnostics_v1-tests.txt)، [manifest فایل‌ها](max4_05_decomposition_diagnostics_v1-source-manifest.json).

