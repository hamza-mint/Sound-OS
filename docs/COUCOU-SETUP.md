# تشغيل Coucou (الجزيرة + Mochi) مع Sound OS

`main.py` بيبعت أحداث لتطبيق **Coucou** الأصلي (https://github.com/Louis-CFM/coucou) عبر الـ socket بتاعه،
والتصميم والأنيميشن بيترسموا من Coucou نفسه (مفيش حاجة من تصميمه متنسخة في الريبو، ده بيحترم رخصة الأصول `LICENSE-ASSETS.md`).

## على Fedora
1. نزّل الـ rpm من https://github.com/Louis-CFM/coucou/releases (ملف `Coucou-Linux-*-x86_64.rpm`) وبعدين:
   `sudo dnf install ./Coucou-Linux-*.rpm`
2. شغّل Coucou (هتلاقيه في قايمة التطبيقات)، هتشوف الجزيرة فوق الشاشة.
3. شغّل `python3 main.py --text "افتح فايرفوكس"`: هيظهر pill اسمه `sound-os` فيه الجملة، وMochi بيفرح لما الأمر ينجح.

## لو Coucou مش شغال
`main.py` بيفتح النافذة المدمجة (Tkinter) تلقائيًا. محتاجة: `sudo dnf install python3-tkinter python3-pillow python3-pillow-tk`.

## التحكم
متغير `SOUNDOS_UI`: `auto` (الافتراضي) / `coucou` / `window` / `both`.
