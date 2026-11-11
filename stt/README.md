# Sound OS - Speech-to-Text module

Offline speech recognition (Arabic Egyptian dialect + English) for Sound OS,
built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper). CPU only, no GPU.

```
Microphone -> Wake word -> [ Speech-to-Text ] -> Intent parser -> Executor -> Voice feedback
```

## Contract

```python
from stt import SpeechToText

stt = SpeechToText("base")                     # load ONCE at startup
text, lang = stt.transcribe(audio)             # audio: WAV path or numpy array
text, lang = stt.transcribe(audio, language="ar")   # optional forced language
```

| | |
|---|---|
| **Input** | WAV path, or numpy array. **16 kHz, mono**, `float32` in [-1, 1] or `int16` |
| **Output** | `(text, lang)`, `lang` is `"ar"` or `"en"` |
| **Empty text** | `""` means "no speech understood" - the caller must ignore it |

`textnorm.normalize(text)` unifies Arabic spelling (إفتح / افتح). It is shared with the intent parser.
It does not fix wrong or missing letters (`المتصف` vs `المتصفح`): use fuzzy matching in the parser.

### Notes for teammates
- **Audio / wake-word owner:** send the audio that comes *after* the wake word, 16 kHz mono. Wrong dtype or sample rate gives empty or garbage text. Files with another sample rate raise `ValueError`.
- **Parser owner:** the confirmation flow needs **yes / no** in both languages (`yes`, `no`, `ايوه`, `لا`); they are in `phrases.csv` so they get tested. Whisper often returns slightly wrong letters, so match fuzzily.
- **Executor / UI owners:** nothing to change; you receive text from the parser.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows      (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```
The model downloads on first run (internet needed once), then works offline.

## Try it

```bash
python stt.py clip.wav          # auto language
python stt.py clip.wav ar       # force Arabic
python -m examples.pipeline_demo   # push-to-talk demo (wake word is a placeholder)
```

## Add your voice to the test set (everyone please)

```bash
python record_set.py --speaker spk01 --condition quiet
python record_set.py --speaker spk01 --condition noisy    # fan / background noise on
```
Use a **different speaker id per person** (`spk02`, `spk03`...). Each run records ~36 clips
(including 2 silence clips: say nothing). With 3 speakers x 2 conditions we exceed the 50-clip target.
Then commit `testset/audio/*.wav` and `testset/references.csv`.
Phone recordings: `ffmpeg -i in.m4a -ar 16000 -ac 1 out.wav` and add a row to `references.csv` by hand.

## Measure

```bash
python eval_wer.py base                 # WER / CER / language accuracy / false triggers / latency (language from the CSV)
python eval_wer.py base --auto          # language not given: decodes ar + en, keeps the more confident
python eval_wer.py base --prompt        # with initial_prompt (off by default)
python bench.py testset/audio base      # latency + RAM (one model per run, on the DEMO machine)
pytest                                  # unit tests (no model download needed)
```
Change one setting at a time and write the numbers down for the test report.
Report the real numbers even if they miss the targets (< 3 s per command, > 85% accuracy).

## Design decisions (and why)

| Decision | Reason |
|---|---|
| Read files with `soundfile`, pass an array | `faster-whisper` + `av` raised `metadata_errors` TypeError on our setup |
| `vad_filter=True`, `max_new_tokens=40`, repetition filter | Silence produced hallucinated/looping text without them |
| `initial_prompt` **off by default** | A long prompt made the model loop on silence; a short one made `tiny` output the prompt phrase ("افتح المتصفح") for other commands |
| Language restricted to `ar`/`en` | On silence/short clips Whisper guessed `nn` (Norwegian) |
| No language given -> decode in **both** `ar` and `en`, keep the more confident | Whisper's own detection labelled Arabic commands as English (tiny, base and small). Forcing the language is faster; this is the fallback. **Not validated on a real test set yet.** `SpeechToText(auto_strategy="whisper")` restores Whisper's detection |
| `run_live.py` stops recording with Silero VAD | A fixed loudness threshold never triggered with the room noise measured on the dev PC |

## Status: what is measured and what is not

Measured only in **live tests on one PC (Ryzen 5 1600, 6 cores, no GPU)** with a handful of clips
(a few English and Arabic commands). These are hints, not results:

| Observation | Detail |
|---|---|
| English commands | `tiny` and `base` transcribed them correctly in most tries |
| Arabic (Egyptian) commands, language forced to `ar` | `tiny` mostly garbled them; `base` and `small` were closer (e.g. `وطي سوت`, `اقفل اجهز`) but still wrong spelling -> the parser must match fuzzily and use a high threshold for dangerous commands |
| Language auto-detection (Whisper) | Often returned `en` for Arabic commands with all three sizes |
| Speed, language forced | tiny ~0.6 s, base ~1.2 s, small ~4.6 s per clip |
| Speed, Whisper auto-detection | about 2x slower than forced (extra detection step) |

Timings varied between runs; re-measure with `bench.py` on the demo laptop.
**The model choice (tiny / base / small) and the auto-language strategy must be decided from
test-set numbers (`record_set.py` + `eval_wer.py`).** `base` is the default only because it was the
best speed/accuracy trade-off in these few live tests.
Not measured yet: WER/CER on a real test set, multiple speakers, noisy conditions, real wake-word audio.

## Repo layout

```
stt.py            the module
textnorm.py       Arabic/English text normalization
record_set.py     record the test set
phrases.csv       phrases to record (with expected intent)
run_live.py       live demo: records until you stop speaking, then transcribes
eval_wer.py       accuracy + latency on the test set
bench.py          latency + RAM
examples/         pipeline_demo.py (how to plug in wake word)
tests/            pytest unit tests
testset/          audio/ + references.csv
```
