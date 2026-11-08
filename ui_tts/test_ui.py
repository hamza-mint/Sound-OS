"""Visual smoke test. From the project root:  python -m ui_tts.test_ui"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui_tts import notify, speak
from ui_tts import coucou_bridge as bar


def talk(seconds):
    """Fake a voice so the waves move."""
    end = time.time() + seconds
    while time.time() < end:
        t = time.time()
        bar.set_level(abs(math.sin(t * 7) * math.sin(t * 2.3)))
        time.sleep(0.05)


print("Opening window (Chris flies in)")
bar.start()
time.sleep(2.0)

print("Standby (robot head bobbing)...")
time.sleep(4)

print("Success case...")
bar.on_wake()
talk(3)
bar.on_heard("open the browser")
time.sleep(1.5)
bar.on_done(True)
notify("Sound OS", "Command executed \u2705")
speak("hello", "en")
time.sleep(3)

print("Failure case...")
bar.on_wake()
talk(2)
bar.on_heard("something unclear")
time.sleep(1)
bar.on_done(False)
time.sleep(3)

input("Done. Press Enter to quit...")
