# تحلیل اجرای واقعی اعتبارسنجی۱۵سؤال — نسخهٔ۰٫۳٫۳
تاریخ تحلیل:۲۴ نوامبر۲۰۲۶

## نتیجهٔ اصلی
هر۴۵رکورد ثبت شده و اجرای۱۵سؤال/۳روش کامل است. کنترل‌گر آزمایشی فعلی در این اجرا ارزش افزودهٔ موردانتظار را نشان نداد:۱۳بار به سقف دو بازیابی رسید،یک بار درخت نامعتبر داشت و تنها پاسخ نهایی آن نیز خلاف مرجع و بدون پشتیبانی رابطهٔ موردسؤال بود. در تطابق دقیق خودکار،Standard با۸از۱۵ جلوتر ازmax4 با۴از۱۵ است. این نتیجه دربارهٔ همین پیاده‌سازی/مجموعه است؛ اثر خالص وابستگی‌هایOperadic جدا نشده است.

## اصالت و بازتولید
اصل ZIP:۸۵۲۰۲۵بایت،۳۹۶ورودی،SHA256=c4deab630bf24359f3a039b354c3d598ddbd27d81f7b5f1e78b66aa02bbc0483.
هویتWindowsکد با نسخهٔمنتشرشده۰٫۳٫۳ برابر است:2b6626f91afabe75751ec68178e03f7a0a2313485e7bfc7a0a51afe984a86bf4. مدلQwen2.5-7B-Instructباrevisionثابت،NF4/float16،RTX3080Ti وCUDA12.8؛بازیابHybridباBGEثابت رویCPU ثبت شده‌اند.۱۵سؤال وپیکره‌ها با مجموعهٔ ثابت،هشlabels وورودی/مبنا تطبیق داشتند. هر۱۵درخت و۴۵trial با۱۹۹پاسخ مدل و۶۹بازیابی ذخیره‌شده عیناً بازپخش شدند؛گزارش نهایی هم دقیقاً بازتولید شد. زمان تاریخیِ هرtrialجایگزین زمان replay نشد. مدل یا retrieval تازه در تحلیل اجرا نشد.

## منشأ سؤال‌ها و محدودیت اصالت دیتاست
۱۵سؤال از یکmirrorعمومی۲۰۰رکوردی باعنوانHotpotQA distractor validation انتخاب شده‌اند، نه ازدانلود مستقیم فایل رسمی کامل. منبعثبت‌شده درmanifest: مخزنNotAbleToFindAUsername/HotpotQA_Dataset،commit6ac268e426770b3c13c84566aaf4b55ce9548352،فایلhotpotqa_distractor_validation.pkl. زمانساخت دسترسی به میزبان اصلی ناموفق ثبت شده بود.

در این تحلیل فایل منبع دوباره دانلود شد؛۱۲۵۴۳۸۲بایت وSHA256=0d2968ed54b43b0403743de7b2886094943a8938b00908baa728603dcbd8ce64. باخواندن محدود بهcontainerهای داده و ردopcodeهای اجرایی،۲۰۰رکورد بازخوانی شد. پس از حذف هم‌پوشانی با سوابق موجود،۱۹۹رکورد واجدشرایط بود. انتخاب ثابت برپایهSHA256شناسه وsaltازقبلثبت‌شده،۸bridgeو۷comparison را دقیقاً بازتولید کرد. هر۱۵رکورد اصلی پروژه،شامل سؤال/جواب/شواهد،عینmirrorهستند؛انتخاب وابسته به نتیجهٔمدل نبوده است.

بااین‌حال،تطابق باmirrorمعادل تأیید تطابق با انتشار رسمی HotpotQA نیست. درخواست تطبیق فعلی بهdataset-server هاجینگ‌فیس با خطای شبکهHTTP tunnel403رد شد؛بنابراین تطبیق مستقل با نسخهٔ رسمی هنوز برقرار نیست. ناسازگاری‌هایcountry/countyوپاسخ جمله‌ای برای سؤال شخص درهمانmirrorوجود دارند. این اجرا باید «اعتبارسنجی۱۵نمونهٔمنتخب ازmirrorمنتسب بهHotpotQA» توصیف شود، نه ارزیابیِتأییدشده روی مجموعهٔ رسمی کامل. دامنهٔ دیده‌نشده‌بودن فقط سوابق دراختیار پروژه بوده،نه اثبات نبودن درپیش‌آموزش مدل. نمونهٔ نمایشی کنسول قبلی مصنوعی بود؛سؤال‌های این اجرای واقعی ازهمینmirrorآمده‌اند.

## معیارهای گزارش اصلی، بدون تغییر پس از دیدن نتیجه
| روش | EM | F1 | میانگین پوشش شواهد مرجعِ بازیابی‌شده | وضعیت‌ها |
|---|---:|---:|---:|---|
| Standard |۸/۱۵=۵۳٫۳۳٪|۵۴٫۱۷٪|۹۴٫۴۴٪|۱۵answered؛۴مورد متن Empty response |
| max4 |۴/۱۵=۲۶٫۶۷٪|۳۳٫۸۵٪|۸۴٫۴۴٪|۱۳answered،۱abstained،۱invalid_plan|
| کنترل‌گر آزمایشی |۰/۱۵|۰٪|۹۰٪|۱۳budget_exhausted،۱answered غلط،۱invalid_plan|

answeredصرفاً وجود رشتهٔ غیرخالی است؛ به معنی پاسخ معتبر یا درست نیست. پوشش شواهد معیار اسناد بازیابی‌شده است، نه صحت استفاده/ارجاع. Citation Faithfulness وPremature Stopping هنوزnullو داوری مستقل درانتظارند؛ بررسی‌های موردی این گزارش داوری مستقل تکمیل‌شده نیستند. شکست‌ها درمخرج۱۵سؤالی هرروش باقی‌اند. نمونه کوچک است وbootstrapگزارش اصلی نیز عدمقطعیت را حذف نمی‌کند.

## هزینه و زمان
| روش | فراخوانی واقعی اختصاصی | بازیابی | توکن واقعی اختصاصی | توکن با سهم تولید طرح | زمان اختصاصی ثانیه | زمان با سهم طرح ثانیه |
|---|---:|---:|---:|---:|---:|---:|
| Standard |۴۵|۲۵|۳۴۶۳۵|۳۴۶۳۵|۱۲۸٫۲۱|۱۲۸٫۲۱|
| max4 |۵۲|۱۶|۳۴۹۹۰|۴۷۴۷۷|۱۶۸٫۴۴|۴۶۹٫۲۰|
| کنترل‌گر |۸۵|۲۸|۸۳۶۸۰|۹۶۱۶۷|۸۱۱٫۱۵|۱۱۱۱٫۹۱|

طرح مشترک۱۵سؤال واقعاً تولید شده:۱۷فراخوانی،۱۲۴۸۷توکن و۳۰۰٫۷۶ثانیه؛۱۴درخت معتبر و۱نامعتبر. این سهم برای مقایسه به هر مسیر درختی شارژ می‌شود اما در مصرف فیزیکی پروژه فقط یک‌بار می‌آید. کل واقعی:۱۹۹فراخوانیLLM،۶۹بازیابی،۱۶۵۷۹۲توکن. جمع‌کردن ستون سهم‌دار،تولیدطرح را دوبار می‌شمارد. آماده‌سازی مشترک بازیاب۱۲٫۴۲ثانیه جداست؛بارگذاری اولیه مدل داخل زمانtrialها نیست. زمانwallسربار نمایش/ذخیره را دارد.

در کنترل‌گر:۴۵ارزیابی گره/۳۸۹۵۴توکن؛۳۸بررسی پشتیبانی گره/۴۱۸۴۷توکن؛۱بررسی هدف اصلی/۱۸۲۲توکن؛۱ارجاع نهایی/۱۰۵۷توکن. افزایش هزینهٔ بررسی‌ها در این اجرا به پاسخ بهتر منجر نشده است.

## مشکل‌های مشاهده‌شده
۱. رد نادرست پاسخ درست: سؤال۳،هر دو تاریخ مرگ و پاسخ George Archainbaud درست بودند؛مدل بررسی،همان تاریخ‌ها را دلیل تناقض دانست.
۲. پذیرش نادرست پاسخ غلط: سؤال۵،Rabatبه‌جایBeijing؛شاهد پایتخت منطقه به‌عنوان شاهد محل سفیر درچین پذیرفته شد،حتی در بررسی سؤال اصلی. شاهد۷:۰ که صریحاً Moroccan ambassador in Beijing را ذکر می‌کند نیز در شواهد بازیابی‌شده حاضر بود. این مثال نشان می‌دهد کنترل‌گر هنوز اتصال موجودیت/ویژگی را تضمین نمی‌کند.
۳. ناپایداری بازبررسی: در۳،۸،۱۰پشتیبانیِ قبلاً پذیرفته‌شده پس از گسترش شواهد از دست رفت؛ابطال محافظه‌کارانهٔ همهٔbindingها هزینه/فرصت شکست اضافه کرد.
۴. میان۳۸گواهی گره،۱۱supported،۱۴رد مدل با قرارداد معتبر و۱۳رد قرارداد کدی وجود دارد. از۱۳رد کدی،۱۱ incomplete/contradictoryو۲quoteنامعتبرند؛اینها۱۳JSONناخوانا نیستند. بررسی rawپاسخ‌هایsupported=true نشان داد۱۰بارvalueعوض‌شده،۸بارهمهٔcandidate_refsنقل نشده‌اند و۲بارquoteعین متن نیست؛این دسته‌ها هم‌پوشان‌اند و نباید جمع شوند. الزام پوشش همهٔrefs و ثبات دقیقvalue بخشی از طراحی فعلی است و ممکن است بیش‌ازحد محدودکننده باشد؛در این تحلیل ضعیف یا حذف نشد.
۵. خطای پاسخ میانی/هدف درخت: در۸ریشه حرفه را به‌جای نام شخص می‌پرسد؛در۱۰نوع ریشهdateاست؛در۱۴ریشهbooleanاست؛در۹نام سکونتگاه با زبان اشتباه می‌شود. اعتبار ساختاری۱۴/۱۵ صحت معنایی نیست.
۶. نیاز به اثبات منفی: در۱۱نبود شاهد منفی دربارهJoseyScott مانعrootشد،باوجود اطلاعات مثبت دربارهIanWatkins. این محدودیت سیاست تکمیل همهٔپیش‌نیازهاست.
۷. طبقه‌بندی نادرست عدم پاسخ: Standardدر۴،۷،۹،۱۲عیناً متن Empty responseبا/بدون نقطه تولید کرده است؛چون غیرخالی استansweredثبت شده. این خطایnumpy/export یا خالی‌شدن فایل نیست؛rawمدل همین رشته‌هاست. امتیازEMاین موارد صفر مانده اما شمارansweredگمراه‌کننده است. دو پاسخ ارجاع نهایی آن نیز rawبه‌شکلrefs=[]و نامعتبر بودند.
۸. خطا/ابهام مرجع و نرمال‌سازی: در۲سؤالcountryدارد ولی مرجع۹۹۸۴بهcountyمربوط است؛در۱۱پرسشنام مرد می‌خواهد اماgoldیک جملهٔ طولانی دربارهگروه است،درحالی‌که هر دوپایهIanWatkinsداده‌اند. در۷trueدرmax4در برابرyesو در۱۵Mumbai,MaharashtraدربرابرMumbai امتیازEMصفر گرفته‌اند. در۱نیز مرجعCharlesEugèneنیازمند بازبینی است. بنابراین این درصدها باید به‌عنوانEMثبت‌شده خوانده شوند،نه دقت معنایی نهایی. هیچgoldیا نمرهٔ اصلی پس ازمشاهدهنتایج تغییر داده نشد؛ممیزی مرجع و قواعد پذیرش باید جدا و برایهمهروش‌ها یکسان باشد.

## تصمیم پژوهشی و قدم بعد پیشنهادی
این کنترل‌گر با این نتایج قابل‌ارتقا به روش برتر نیست. اول ممیزی مستقل۱۵پرسش/مرجع،پاسخ‌ها وارجاع‌ها؛سپس مشخص‌کردن سهم رد نادرست داور،قرارداد گواهی و سیاست وابستگی در شکست‌ها. OC-ABLATION-01هنوز باز است؛مقایسهٔسهروش اثر خالص وابستگی را جدا نمی‌کند. افزایش بودجه یا ادعای حل با تغییرپرامپت دراین تحلیل انجام نشده است. کد/بودجه/درخت/labelsتغییر نکردند. مبنای پذیرفته‌شدهٔتجزیه max4باقی است.

۱۵سؤال اکنون واقعاً اجرا و نتایجشان مشاهده شده‌اند؛اگر برای طراحی/اصلاح بعدی استفاده شوند،مجموعهٔاعتبارسنجی/توسعه‌اند و آزمون نهاییِ مستقلِ دیده‌نشدهٔ بعدی نخواهند بود. ازپاک‌کردنmarkerیا بازنامیدن همان۱۵به‌عنواندیده‌نشده خودداری شود.

## بررسی هر سؤال

1. Which  French ace pilot and adventurer fly L'Oiseau Blanc
شناسه: 5ae0361155429925eb1afc2c
مرجع ثبت‌شده: Charles Eugène
standard: François Coli — answered
max4: Charles Nungesser and François Coli — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: سؤال یک خلبان تک‌نفره می‌خواهد؛ max4 دو نام داده و مرجع Charles Eugène کوتاه/نیازمند بازبینی است. کنترل‌گر پاسخ را نپذیرفت.

2. Brown State Fishing Lake is in a country that has a population of how many inhabitants ?
شناسه: 5a75e05c55429976ec32bc5f
مرجع ثبت‌شده: 9,984
standard: 9,984 — answered
max4: 9,984 — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: ناسازگاری سؤال/مرجع: متن country می‌گوید ولی مرجع 9,984 جمعیت شهرستان است. درخت کشور United States را دنبال کرد؛ داور نیز همان جواب را بعداً رد کرد.

3. Who died first, George Archainbaud or Ralph Murphy?
شناسه: 5a7a455c5542994f819ef1a7
مرجع ثبت‌شده: George Archainbaud
standard: George Archainbaud — answered
max4: George Archainbaud — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: دو تاریخ مرگ درست و پاسخ George Archainbaud موجود بود؛ داور به‌اشتباه آن را متناقض دانست. بازبررسی دور دوم پشتیبانی قبلی را از دست داد.

4. Do the drinks Gibson and Zurracapote both contain gin?
شناسه: 5ae224da554299234fd043ee
مرجع ثبت‌شده: no
standard: Empty response. — answered
max4: (بدون پاسخ) — abstained
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard عبارت Empty response. را answered ثبت کرد؛ max4 پاسخ نداد. درخت به‌جای صرف وجود gin دربارهٔ مادهٔ اصلی می‌پرسد و پاسخ میانی no نامتناسب است.

5. In which city is the ambassador of the Rabat-Salé-Kénitra administrative region to China based?
شناسه: 5adccd795542990d50227d2c
مرجع ثبت‌شده: Beijing
standard: Rabat — answered
max4: Rabat — answered
operadic: Rabat — answered
یافته: همه Rabat دادند، مرجع Beijing است. درخت هدف محل سفیر در چین را به پایتخت منطقه منحرف کرد؛ کنترل‌گر و بررسی سؤال اصلی همان ارجاع پایتخت را پذیرفتند.

6. Vince Phillips held a junior welterweight title by an organization recognized by what larger Hall of Fame?
شناسه: 5a8361b65542992ef85e22a0
مرجع ثبت‌شده: International Boxing Hall of Fame
standard: International Boxing Hall of Fame — answered
max4: IBF — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard پاسخ Hall of Fame مرجع را داد؛ max4 سازمان IBF را تکرار کرد. در کنترل‌گر پاسخ گره دوم و گواهی/نقل‌قول بعدی مشکل داشت.

7. Were Scott Derrickson and Ed Wood of the same nationality?
شناسه: 5a8b57f25542995d1e6f1371
مرجع ثبت‌شده: yes
standard: Empty response — answered
max4: true — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard عبارت Empty response داد؛ max4 با true به مرجع yes پاسخ معنایی نزدیک دارد ولی EM صفر است. پاسخ‌های میانی ملیت و گواهی‌های کنترل‌گر ناپایدار بودند.

8. Which American film director hosted the 18th Independent Spirit Awards in 2002?
شناسه: 5ac3165c5542995ef918c10a
مرجع ثبت‌شده: John Waters
standard: John Waters — answered
max4: film director — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard نام John Waters را داد؛ ریشهٔ درخت حرفه را می‌پرسد و max4 film director پاسخ داد. کنترل‌گر میزبان را ابتدا پذیرفت و در بازبررسی بعدی رد کرد.

9. When was the Western Germanic language spoken from which the small settlement situated on the river Leda opposite Leer derives its name?
شناسه: 5a8eea4a5542990e94052bb7
مرجع ثبت‌شده: between the 8th and 16th centuries
standard: Empty response — answered
max4: between 8th and 16th centuries — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard عبارت Empty response داد؛ max4 بازهٔ زمانی مطابق مرجع داد. کنترل‌گر برای نام سکونتگاه Old Frisian پاسخ داد؛ موجودیت/ویژگی اشتباه است.

10. Which was fought earlier in our nation's history, the Seven Days Battles or the Battle of Manila?
شناسه: 5a7633ad5542992db9473741
مرجع ثبت‌شده: The Seven Days Battles
standard: Seven Days Battles — answered
max4: June 25, 1862 — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard نام نبرد درست را داد؛ نوع ریشه date است و max4 تاریخ داد. کنترل‌گر با ناپایداری پذیرش تاریخ‌ها متوقف شد.

11. Josey Scott and Ian Watkins were both promising musicians. Which of these talented men was incarcerated, impacting his career with a rock band?
شناسه: 5ac298f9554299657fa28fc9
مرجع ثبت‌شده: Lostprophets disbanded in 2013 after Watkins was charged with sexual offences in late 2012.
standard: Ian Watkins — answered
max4: Ian Watkins — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: هر دو روش پایه Ian Watkins دادند؛ مرجع یک جمله دربارهٔ گروه است، نه نام مرد خواسته‌شده، لذا EM نیازمند ممیزی مرجع است. کنترل‌گر بر نبود شاهد منفی دربارهٔ Josey Scott متوقف شد.

12. Which performance act has a higher instrument to person ratio, Badly Drawn Boy or Wolf Alice?
شناسه: 5ae2070a5542994d89d5b313
مرجع ثبت‌شده: Badly Drawn Boy
standard: Empty response. — answered
max4: (بدون پاسخ) — invalid_plan
operadic: (بدون پاسخ) — invalid_plan
یافته: درخت پس از دو تلاش نامعتبر ماند؛ هر دو روش درختی invalid_plan شدند و بازیابی نداشتند. Standard عبارت Empty response. داد.

13. Are Broughtonia and Laeliocattleya both orchids?
شناسه: 5ab642845542995eadeeff8e
مرجع ثبت‌شده: yes
standard: Yes. — answered
max4: yes — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard وmax4 yes درست دادند. کنترل‌گر به سؤال طبقه‌بندی، yes جواب می‌داد؛ قرارداد گواهی و پاسخ نامتناسب مانع تکمیل شدند.

14. What is the name of the singer who's song was released as the lead single from the album "Confessions", and that had popular song stuck behind for eight consecutive weeks?
شناسه: 5ae7ba7a5542993210983f12
مرجع ثبت‌شده: Usher
standard: Usher — answered
max4: false — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard Usher داد؛ درخت ریشهٔ boolean دارد و max4 false داد. در کنترل‌گر گواهی نام Usher مقدار پیشنهادی را عوض کرد و دو بار رد شد.

15. Where is the company that Sachin Warrier worked for as a software engineer headquartered?
شناسه: 5a74106b55429979e288289e
مرجع ثبت‌شده: Mumbai
standard: Mumbai — answered
max4: Mumbai, Maharashtra — answered
operadic: (بدون پاسخ) — budget_exhausted
یافته: Standard Mumbai مطابق مرجع داد؛ max4 Mumbai, Maharashtra داد و EM صفر شد. در کنترل‌گر گره تشخیص شرکت بی‌پاسخ ماند.
