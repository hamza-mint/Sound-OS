"""Visual smoke test. Run from the project root:  python3 -m ui_tts.test_ui"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui_tts import notify, speak
from ui_tts import coucou_bridge as bar

print("Success case...")
bar.on_wake()
time.sleep(1.5)
bar.on_heard("open the browser")
time.sleep(2)
bar.on_done(True)
notify("Sound OS", "Command executed \u2705")
speak("hello", "en")
time.sleep(2.5)

print("Failure case...")
bar.on_wake()
time.sleep(1)
bar.on_heard("something unclear")
time.sleep(1.5)
bar.on_done(False)
time.sleep(2.5)
print("Done.")
