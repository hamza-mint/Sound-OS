import numpy as np

try:
    from stt.run_live import Endpointer, SR
except ImportError:
    from run_live import Endpointer, SR


def fake_vad_factory(speech_spans):
    """speech_spans: [(start_s, end_s)] -> دالة VAD وهمية بترجّع بس اللي اتسجّل لحد دلوقتي."""
    def vad(audio):
        total = len(audio) / SR
        return [{"start": int(s * SR), "end": int(min(e, total) * SR)}
                for s, e in speech_spans if s < total]
    return vad


def run(ep, spans_total):
    """بيحاكي التسجيل كل 0.3 ثانية ويرجّع (state, الوقت اللي وقف عنده)."""
    t = 0.0
    while t < 60:
        t += 0.3
        audio = np.zeros(int(t * SR), dtype=np.float32)
        state, end = ep.update(audio)
        if state in ("done", "no_speech", "max"):
            return state, round(t, 1)
    return "never", t


def test_stops_after_silence_following_speech():
    ep = Endpointer(silence_seconds=3.0, vad=fake_vad_factory([(1.0, 3.0)]))
    state, t = run(ep, None)
    assert state == "done" and 6.0 <= t <= 6.5          # 3.0 (آخر كلام) + 3 سكوت


def test_pause_shorter_than_threshold_does_not_stop():
    # كلام 1-2 ، وقفة ثانيتين ، كلام 4-6  -> لازم يكمل لحد 6 + 3
    ep = Endpointer(silence_seconds=3.0, vad=fake_vad_factory([(1, 2), (4, 6)]))
    state, t = run(ep, None)
    assert state == "done" and 9.0 <= t <= 9.5


def test_late_start_is_not_cut_off():
    # الكلام بدأ بعد 5 ثواني: مينفعش يقف قبله
    ep = Endpointer(silence_seconds=3.0, wait_seconds=8.0, vad=fake_vad_factory([(5, 6)]))
    state, t = run(ep, None)
    assert state == "done" and t >= 9.0


def test_nobody_speaks_gives_up():
    ep = Endpointer(wait_seconds=8.0, vad=fake_vad_factory([]))
    state, t = run(ep, None)
    assert state == "no_speech" and 8.0 <= t <= 8.4


def test_max_length_cap():
    ep = Endpointer(silence_seconds=3.0, max_seconds=20.0, vad=fake_vad_factory([(1, 100)]))
    state, t = run(ep, None)
    assert state == "max" and 20.0 <= t <= 20.4


def test_real_silero_on_noise_and_silence_never_triggers():
    rng = np.random.default_rng(0)
    ep = Endpointer()                                    # Silero الحقيقي
    noise = (rng.standard_normal(SR * 10) * 0.014).astype(np.float32)
    assert ep.update(noise)[0] == "no_speech"            # ضوضاء بقوة اللي قستها
    assert ep.update(np.zeros(SR * 3, dtype=np.float32))[0] == "waiting"


def test_first_start_is_recorded():
    ep = Endpointer(vad=fake_vad_factory([(1.5, 2.5)]))
    ep.update(np.zeros(int(3.0 * SR), dtype=np.float32))
    assert ep.first_start == 1.5
