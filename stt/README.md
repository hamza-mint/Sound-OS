# Sound OS - Speech-to-Text module

Offline speech recognition (Arabic Egyptian dialect + English) for Sound OS,
built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper). CPU only, no GPU.

```
Microphone -> Wake word -> [ Speech-to-Text ] -> Intent parser -> Executor -> Voice feedback
```

## Contract

```python
from stt import SpeechToText

stt = SpeechToText("tiny")                     # load ONCE at startup
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
python eval_wer.py tiny                 # WER / CER / language accuracy / false triggers / latency
python eval_wer.py tiny --auto          # with language auto-detection
python eval_wer.py tiny --no-prompt     # compare with / without initial_prompt
python bench.py testset/audio tiny      # latency + RAM (one model per run, on the DEMO machine)
pytest                                  # unit tests (no model download needed)
```
Change one setting at a time and write the numbers down for the test report.
Report the real numbers even if they miss the targets (< 3 s per command, > 85% accuracy).

## Design decisions (and why)

| Decision | Reason |
|---|---|
| Read files with `soundfile`, pass an array | `faster-whisper` + `av` raised `metadata_errors` TypeError on our setup |
| `vad_filter=True`, `max_new_tokens=24`, repetition filter | Silence produced hallucinated/looping text without them |
| One **short** `initial_prompt` sentence | A long list of command words made the model repeat those words on silence |
| Language restricted to `ar`/`en` | On silence/short clips Whisper guessed `nn` (Norwegian) |

## Status: what is measured and what is not

Measured so far on **one PC (Ryzen 5 1600, 6 cores, no GPU)** with only **3 clips**
(one Arabic phrase, one English phrase, one silence). These are hints, not results:

| Model | Time per clip | Notes |
|---|---|---|
| tiny | ~1.2-1.5 s | correct on both phrases, silence returned empty |
| base | ~3.6-3.7 s | Arabic correct with prompt; English clip detected as Arabic (1 clip only) |
| small | ~5 s | slower than the 2-3 s target on this PC |

Timings varied between runs on the same machine, so they must be re-measured with `bench.py`
on the demo laptop. **The model choice (tiny vs base vs small) is decided from the test-set numbers, not from these.**
Not measured yet: WER/CER on a real test set, multiple speakers, noisy conditions, real wake-word audio.

## Repo layout

```
stt.py            the module
textnorm.py       Arabic/English text normalization
record_set.py     record the test set
phrases.csv       phrases to record (with expected intent)
eval_wer.py       accuracy + latency on the test set
bench.py          latency + RAM
examples/         pipeline_demo.py (how to plug in wake word)
tests/            pytest unit tests
testset/          audio/ + references.csv
```
