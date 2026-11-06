# 🎙️ Sound OS — تقرير الفريق الشامل | Team Brief & Status

> **آخر تحديث:** 6 نوفمبر 2026  
> **حالة المشروع:** المرحلة الأولى (Foundation) مكتملة ومدموجة في `main` بنسبة نجاح 100% (214 tests passed ✅).  
> **الهدف:** توضيح الوضع الحالي للريبو، ما تم إنجازه، وخارطة طريق واضحة لكل عضو في الفريق لدوره القادم.

---

## 🗺️ أولاً: خريطة الـ Pipeline الشاملة

المشروع عبارة عن طبقة تحكم صوتية فوق نظام Linux (Xubuntu / Xfce).  
المستخدم يعطي أمراً صوتياً بالعامية المصرية أو بالإنجليزية، والنظام ينفّذه محلياً بالكامل (Offline-first).

```
🎙️ ميكروفون
      ↓
🔔 [Role 1] Audio & Wake Word       ← Abram           [الفرع: Abram-(Audio-WakeWord)]
      ↓  (ملف صوتي WAV 16kHz)
🗣️ [Role 2] Speech-to-Text          ← Mahmoud Hamed   ✅ مدموج في main
      ↓  ({"text": "...", "lang": "ar"|"en"})
🧠 [Role 3] Intent Parser           ← Kurollos (Kero) ✅ مدموج في main
      ↓  (JSON بأمر محدد ومعايير واضحة)
🤖 [Backup] Qwen3 Fallback (Ollama)  ← Kurollos        ✅ مدموج في main (اختياري)
      ↓
🛡️ [Role 4] Safety Layer            ← Antonius        [الفرع: Antonius-(Safety)]
      ↓  ({"decision": "allow"|"confirm"|"block"})
⚙️ [Role 5] Command Executor        ← Yassin          [الفرع: Yassin-(Executor)]
      ↓  ({"success": true/false, "message": "..."})
🔊 [Role 6] UI & TTS Feedback       ← Youssef Alam    [الفرع: Youssef-(UI-TTS)]
```

**فرق الجودة والاختبار المستمر:**
- 🎙️ **Role 7 — QA & Soundsets:** Kirollos Ibrahim `[الفرع: KirollosIbrahim-(QA)]`
- 🧪 **Role 8 — Automated Testing & Benchmarks:** Kareem Waleed `[الفرع: Kareem-(AutoTesting)]`

---

## 🤝 ثانياً: العقد الموحد (The Unified Interface Contract)

> [!IMPORTANT]
> العقد الرسمي موجود في أصل المشروع [`CONTRACT.md`](../CONTRACT.md).  
> جميع الموديولز تعمل بالفعل الآن بفضل الـ Stubs المجهزة مسبقاً — لا أحد ينتظر الآخر للبدء!  
> الأمر `python main.py --text "افتح فايرفوكس"` يعمل الآن من اليوم الأول.

### ملخص شكل البيانات المتبادلة بين المكونات:

#### 1. مخرجات الـ STT (محمود) ⬅ الـ Parser (كيرلس):
```json
{
  "text": "افتح فايرفوكس",
  "lang": "ar",
  "confidence": 0.95
}
```

#### 2. مخرجات الـ Intent Parser (كيرلس) ⬅ الـ Safety (أنتونيوس):
```json
{
  "intent": "open_app",
  "params": { "app": "firefox" },
  "lang": "ar",
  "raw_text": "افتح فايرفوكس"
}
```

#### 3. مخرجات الـ Safety Layer (أنتونيوس) ⬅ الـ Executor (ياسين):
```json
{
  "decision": "allow",
  "message": "الأمر آمن للتنفيذ"
}
```
*(أو `"decision": "confirm"` للأوامر الخطرة مثل إغلاق الجهاز وحذف الملفات).*

#### 4. مخرجات الـ Executor (ياسين) ⬅ الـ UI/TTS (يوسف علام):
```json
{
  "success": true,
  "message": "تم فتح المتصفح"
}
```

---

## 📊 ثالثاً: حالة الإنجاز الحالي في الريبو (`main`)

### 1. ما تم إنجازه ودمجه بنجاح ✅

| الموديول | العضو | الحالة | ملخص ما تم تنفيذه |
|---|---|---|---|
| **Speech-to-Text (`stt/`)** | **Mahmoud Hamed** | ✅ منجز ومدموج | نموذج `faster-whisper` مدمج مع تطبيع اللهجة المصرية `textnorm.py`، واختبارات قياس WER ومعدل السرعة `bench.py`. |
| **Intent Parser (`intent_parser/`)** | **Kurollos (Kero)** | ✅ منجز ومدموج | محرك تحليل الأوامر المبني على القواعد (Regex + RapidFuzz) يغطي 13 أمراً بنسبة دقة **100% على 190 جملة اختبار**. دعم العامية المصرية والإنجليزية بالكامل. |
| **LLM Fallback (`intent_parser/llm_fallback.py`)** | **Kurollos (Kero)** | ✅ منجز ومدموج | ربط احتياطي بموديل Qwen3 عبر Ollama في حال لم تطابق القواعد، ومضبوط بـ timeout وحماية لمنع توليد أوامر خطرة. |
| **Pipeline Glue (`main.py`)** | **Kurollos (Kero)** | ✅ منجز ومدموج | شريان الربط الذي يستدعي كافة الدوال بالترتيب القانوني، ويدعم وضع التجربة النصية بدون ميكروفون `--text`. |
| **Stubs لكافة الأدوار** | الفريق | ✅ جاهزة في main | مجلدات `audio/`, `safety/`, `executor/`, `ui_tts/` تحوي كوداً أولياً يطبق العقد تماماً لتشغيل الاختبارات. |
| **مجموعة الاختبارات (`tests/`)** | Kareem / Kero | ✅ 214 اختبار ينجح | جميع اختبارات العقد (Contract tests) والـ Parser و الـ Textnorm تمر بنجاح كامل في أقل من 5 ثوانٍ. |

---

## 🎯 رابعاً: خطة العمل المباشرة لكل دور قادم

تم إنشاء فرع مستقل لكل عضو مشتق مباشرة من أحدث نسخة لـ `main`:

```bash
# للبدء في العمل على فرعك الخاص:
git fetch origin
git checkout <اسم-فرعك>
git pull origin <اسم-فرعك>
```

---

### 1️⃣ دور أبرام — Audio & Wake Word
- **الفرع المخصص:** `Abram-(Audio-WakeWord)`
- **المجلد الخاص به:** `audio/`
- **الدوال المطلوبة (حسب CONTRACT.md):**
  1. `wait_for_wake_word() -> None`: دالة تحجب (blocks) حتى يتم سماع كلمة التنبيه (Wake Word).
  2. `record_utterance(max_seconds=6.0) -> str`: تسجل صوت المستخدم حتى يتوقف عن الكلام، وترجع مسار ملف صوتي `WAV` (معدل 16kHz mono).
- **الخطوة الأولى:** استخدام `openwakeword` أو `porcupine` لتسجيل كلمة التنبيه واختبار التقاط الصوت مع VirtualBox/Linux.

---

### 2️⃣ دور أنتونيوس — Safety Layer
- **الفرع المخصص:** `Antonius-(Safety)`
- **المجلد الخاص به:** `safety/`
- **الدوال المطلوبة (حسب CONTRACT.md):**
  - `check(parsed: dict) -> dict`:
    - ترجع `{"decision": "allow", "message": "..."}` للأوامر العادية (`open_app`, `volume_up`, ...).
    - ترجع `{"decision": "confirm", "message": "هل أنت متأكد؟"}` للأوامر الخطرة (`shutdown`, `delete_file`).
    - ترجع `{"decision": "block", "message": "أمر محظور"}` لأي أمر مجهول أو محظور (مثل `rm -rf` أو تعديل خارج مسار مجلد النظام).
- **الخطوة الأولى:** بناء جدول الـ Allowlist والتحقق من عدم السماح بحذف أي ملف خارج مجلد `~/SoundOS_Files/`.

---

### 3️⃣ دور ياسين — Command Executor
- **الفرع المخصص:** `Yassin-(Executor)`
- **المجلد الخاص به:** `executor/`
- **الدوال المطلوبة (حسب CONTRACT.md):**
  - `execute(parsed: dict) -> dict`:
    - تنفيذ الأمر الفعلي عبر أدوات لينكس (`pactl` للصوت، `brightnessctl` للسطوع، `xdg-open` أو `subprocess.Popen` لتشغيل البرامج، `gio trash` لحذف الملفات بأمان).
    - احترام البيئة الآمنة: إذا كان المتغير `SOUNDOS_DRY_RUN=1` مفعل، لا ينفذ الأمر فعلياً بل يسجل فقط.
- **الخطوة الأولى:** كتابة دوال التحكم بالصوت والتطبيقات وتجربتها مباشرة عبر الـ Terminal.

---

### 4️⃣ دور يوسف علام — الواجهة الرسومية (GUI Only)
- **الفرع المخصص:** `Youssef-(UI-TTS)`
- **المجلد الخاص به:** `ui_tts/`
- **الدليل التفصيلي المجهز له:** يرجى قراءة [`docs/Youssef-UI-Guide.md`](./Youssef-UI-Guide.md)
- **نطاق الدور (مبسط ومباشر):**
  - دور علام مقتصر فقط على **الواجهة الرسومية (GUI)** وإشعار سطح المكتب، دون أي تعقيد في النماذج الصوتية.
- **المهام المطلوبة منه في مجلده:**
  1. `ui_tts/coucou_bridge.py`: إظهار شريط الجزيرة العائم في أعلى الشاشة (`on_wake`, `on_heard`, `on_done`).
  2. `ui_tts/__init__.py`: إرسال إشعار سطح المكتب `notify()`.
  3. `ui_tts/test_ui.py`: سكربت تجربة سريع لرؤية الواجهة تعمل على الشاشة.
- **الرفع:** يرفع عمله مباشرة إلى مجلده `ui_tts/` على فرعه `Youssef-(UI-TTS)`.

---

### 5️⃣ دور كيرلس إبراهيم — QA & Test Audio Sets
- **الفرع المخصص:** `KirollosIbrahim-(QA)`
- **المجلد المخصص له:** `testdata/`
- **المهام المطلوبة:**
  1. تسجيل ملفات صوتية واقعية (WAV 16kHz) من أشخاص مختلفين (3 متحدثين على الأقل) تمثل الأوامر الـ 13 بالعربي والإنجليزي في بيئات هادئة ومشوشة.
  2. توثيق حالات الاختبار ومتابعة قياس دقة الـ STT و الـ Parser.

---

### 6️⃣ دور كريم وليد — Automated Testing & CI
- **الفرع المخصص:** `Kareem-(AutoTesting)`
- **المجلد المخصص له:** `tests/`
- **المهام المطلوبة:**
  1. كتابة اختبارات تكامل (End-to-End Tests) تحاكي تدفق البيانات من ملفات الصوت حتى المخرجات النهائية.
  2. كتابة سكربت لحساب Word Error Rate (WER) واختبارات الـ Benchmark للسرعة واستهلاك الذاكرة.
  3. التأكد الدائم من بقاء الاختبارات خضراء في الـ CI (`pytest`).

---

## 🔒 القواعد الذهبية للفريق (Team Rules)

1. **الفرع الرئيسي `main` مقدس:** لا أحد يقوم بالرفع المباشر (`git push origin main`). كل عضو يعمل في فرعه، وتتم المراجعة والدمج بعد التأكد من نجاح الـ pytest.
2. **لا تلمس مجلد غيرك:** كل عضو يعدل حصراً في المجلد الخاص به (`audio/`, `safety/`, `executor/`, `ui_tts/`).
3. **الدوال لا ترفع استثناءات (Never Raise Exceptions):** في حال حدوث أي خطأ، يتم إرجاع قيمة خطأ مهذبة (`success: false` أو `decision: "block"`) لضمان عدم توقف النظام ككل.
4. **العقد هو الحكم:** أي تعديل في صيغة الـ JSON أو أسماء الدوال يتطلب تحديث [`CONTRACT.md`](../CONTRACT.md) بموافقة الفريق.

---

## 🚀 كيفية تشغيل واختبار المشروع الآن

```bash
# 1. تفعيل البيئة الافتراضية
source .venv/bin/activate

# 2. تشغيل كافة الاختبارات للتأكد من سلامة النظام
pytest -q

# 3. تجربة النظام كاملاً عبر سطر الأوامر (محاكاة أمر صوتي)
python main.py --text "افتح فايرفوكس"
python main.py --text "ارفع الصوت"
python main.py --text "open terminal"
```
