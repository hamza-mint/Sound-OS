# 📚 دليل التوثيق والتقارير | Documentation Hub

مرحباً بك في مركز التوثيق والتقارير لمشروع **Sound OS**.  
هذا المجلد يحتوي على كافة الوثائق الهندسية، تقارير الفريق، خطط العمل، والأدلة الفنية الخاصة بكل عضو.

---

## 🗂️ فهرس المستندات (Documentation Index)

### 1. خطط وتقارير الفريق (Team Planning & Status)
* [**`TEAM_BRIEF.md`**](./TEAM_BRIEF.md) — **تقرير الفريق وخارطة الأدوار الشاملة**  
  يشرح وضع المشروع الحالي، حالة كل موديول، ما تم إنجازه، ودور كل عضو بالخطوات التفصيلية ومسارات الفروع.
* [**`TEAM_PLAN.md`**](./TEAM_PLAN.md) — **الخطة الزمنية (3-Week Sprint Plan)**  
  قواعد العمل بالفروع (Branching Rules)، جدول المهام اليومي، إدارة الـ Blockers، ونظام الـ 15-Minute Stand-up.
* [**`ANALYSIS.md`**](./ANALYSIS.md) — **التحليل المعماري والقرارات التقنية**  
  شرح معمارية الـ Pipeline، دراسة كفاءة النماذج (Faster-Whisper & Qwen3 Fallback)، معالجة اللهجة المصرية، ومقاييس الأداء.

---

### 2. أدلة الأدوار والتقنيات (Guides & Manuals)
* [**`Abram-Audio-Guide.md`**](./Abram-Audio-Guide.md) — **دليل أبرام (Audio & Wake Word)**  
  دليل تطبيقي مبسط ومباشر لموديول الصوت: التقاط الميكروفون، كشف كلمة التنبيه، تسجيل الصوت بصيغة 16kHz Mono WAV لـ Whisper، طريقة الاختبار البسيطة، وأوامر الرفع لفرعه الخاص على GitHub.
* [**`Youssef-UI-Guide.md`**](./Youssef-UI-Guide.md) — **دليل يوسف علام (GUI & Desktop Notifications)**  
  دليل تطبيقي مبسط ومباشر مخصص للواجهة الرسومية فقط (GUI): إظهار الشريط العائم التفاعلي (Floating Island Pill)، إشعارات سطح المكتب عبر `notify-send`، طريقة الاختبار البصري السريعة، وأوامر الرفع لفرعه الخاص على GitHub.
* [**`LLM-setup.md`**](./LLM-setup.md) — **دليل إعداد وتشغيل النماذج المحلية (Ollama & Qwen)**  
  خطوات تثبيت وتشغيل نماذج الذكاء الاصطناعي محلياً عبر Ollama واستخدامها كـ Fallback للـ Intent Parser.
* [**`llm-basics.md`**](./llm-basics.md) — **المفاهيم الأساسية لنماذج اللغة (LLM Basics)**  
  شرح مبسط لمصطلحات النماذج اللغوية، الأوزان، الـ Quantization، واستهلاك الذاكرة.

---

### 3. التقارير الأسبوعية (Weekly Reports)
* [**`weekly-reports/`**](./weekly-reports/) — مجلد التقارير الأسبوعية والعروض التقديمية لمتابعة تسليمات المشروع الجامعي.

---

## 🤝 العقد الموحد للمشروع (Interface Contract)

جميع الموديولات تلتزم بالعقد الموحد المعرف في أصل المستودع:  
👉 [**`CONTRACT.md`**](../CONTRACT.md)

---

## 🌿 فروع أعضاء الفريق على GitHub (Branches)

تم تجهيز فرع لكل دور مشتق مباشرة من `main` ليعمل كل عضو باستقلالية تامة:

| العضو | الدور | الفرع على GitHub |
|---|---|---|
| **Abram** | Audio Capture & Wake Word | `Abram-(Audio-WakeWord)` |
| **Mahmoud Hamed** | Speech-to-Text | `Mahmoud-Hamed-(Speech-to-Text)` *(مدموج في main)* |
| **Kurollos (Kero)** | Intent Parser Engine | `Kurollos-(Intent-Parser)` *(مدموج في main)* |
| **Antonius** | Safety Layer & Allowlist | `Antonius-(Safety)` |
| **Yassin** | Command Executor | `Yassin-(Executor)` |
| **Youssef Alam** | UI & TTS Voice Feedback | `Youssef-(UI-TTS)` |
| **Kirollos Ibrahim** | QA & Voice Testsets | `KirollosIbrahim-(QA)` |
| **Kareem Waleed** | Automated Testing & Benchmarks | `Kareem-(AutoTesting)` |

---

## 🧪 التحقق من جاهزية النظام

للتأكد من أن كافة الاختبارات تمر بنجاح:
```bash
# تفعيل البيئة وتشغيل pytest
source .venv/bin/activate
pytest -q
```
**النتيجة المتوقعة:** `214 passed`
