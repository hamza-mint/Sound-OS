import time
try:
    from safety import SafetyLayer
except ImportError:
    from safety_layer import SafetyLayer


def run_safety_demo():
    # بنعمل نسخة من طبقة الأمان بـ cooldown مدته 10 ثواني للتجربة السريعة
    safety = SafetyLayer()
    safety.cooldown_seconds = 10.0

    # دوال وهمية (Mocks) تحاكي واجهة وصوت Youssef أثناء الاختبار
    def mock_ui_state(state, text=None):
        print(f"   [UI State -> {state}] {text or ''}")

    def mock_tts_speak(msg, lang):
        print(f"   [TTS ({lang}) -> Speaking]: {msg}")

    test_cases = [
        (
            "1. أمر آمن ومسموح (فتح متصفح فايرفوكس)",
            {"intent": "open_app", "params": {"app": "firefox"}, "lang": "ar", "raw_text": "افتح المتصفح", "confidence": 0.94},
            None,
        ),
        (
            "2. تفعيل خاطئ لكلمة التنشيط (نص فاضي)",
            {"intent": "volume_up", "params": {}, "lang": "ar", "raw_text": " ", "confidence": 0.90},
            None,
        ),
        (
            "3. أمر مسموع غلط في دوشة (Confidence قليل 0.45)",
            {"intent": "mute", "params": {}, "lang": "ar", "raw_text": "اكتم الصوت", "confidence": 0.45},
            None,
        ),
        (
            "4. أمر بره قائمة السماح (Intent غير معتمد)",
            {"intent": "install_malware", "params": {}, "lang": "en", "raw_text": "install malware", "confidence": 0.99},
            None,
        ),
        (
            "5. محاولة فتح برنامج غير مسموح (Terminal Hacker Tool)",
            {"intent": "open_app", "params": {"app": "nmap"}, "lang": "en", "raw_text": "open nmap", "confidence": 0.91},
            None,
        ),
        (
            "6. محاولة مسح ملف نظام حساس (Path Traversal Attack)",
            {"intent": "delete_file", "params": {"path": "../../etc/passwd"}, "lang": "en", "raw_text": "delete passwd", "confidence": 0.95},
            lambda timeout: "yes",
        ),
        (
            "7. أمر خطير (shutdown) والمستخدم رفض وقال 'لأ'",
            {"intent": "shutdown", "params": {}, "lang": "ar", "raw_text": "اطفي الجهاز", "confidence": 0.96},
            lambda timeout: "لأ الغاء",
        ),
        (
            "8. أمر خطير (shutdown) والمستخدم سكت أكتر من 5 ثواني (Timeout)",
            {"intent": "shutdown", "params": {}, "lang": "ar", "raw_text": "اطفي الجهاز", "confidence": 0.96},
            lambda timeout: (time.sleep(5.2), "أيوة")[1],
        ),
        (
            "9. أمر خطير (shutdown) والمستخدم وافق خلال 5 ثواني",
            {"intent": "shutdown", "params": {}, "lang": "ar", "raw_text": "اطفي الجهاز", "confidence": 0.96},
            lambda timeout: "أيوة موافق",
        ),
        (
            "10. تكرار نفس الأمر الخطير (shutdown) فوراً لاختبار الـ Cooldown",
            {"intent": "shutdown", "params": {}, "lang": "ar", "raw_text": "اطفي الجهاز", "confidence": 0.96},
            lambda timeout: "أيوة",
        ),
    ]

    print("=" * 65)
    print("         SOUND OS - SAFETY LAYER TEST SUITE (ANTONIUS)")
    print("=" * 65)

    all_passed = True
    for title, cmd, listener in test_cases:
        print(f"\n[TEST] {title}")
        result = safety.check(
            parsed_command=cmd,
            speak_fn=mock_tts_speak,
            update_state_fn=mock_ui_state,
            listen_yes_no_fn=listener,
        )
        status = "✅ APPROVED" if result["approved"] else "❌ REJECTED"
        print(f"   Result : {status}")
        print(f"   Reason : {result['reason']}")

    return all_passed


if __name__ == "__main__":
    run_safety_demo()
