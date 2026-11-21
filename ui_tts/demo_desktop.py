"""Dave on the desktop, talking. From the project root:  python -m ui_tts.demo_desktop

Dave flies in saying hello, listens, "hears" a command, and answers out loud: his mouth moves
with the voice and his speech bubble shows the words. Drag him, click him, or right-click
him for a menu. (If the voice file is missing he still shows the words in his bubble.)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui_tts import dave_desktop as dave
from ui_tts import dave_voice, speak


def wait_until_quiet(limit=30):
    t = time.perf_counter()
    time.sleep(0.2)
    while dave_voice.is_speaking() and time.perf_counter() - t < limit:
        time.sleep(0.05)


def main():
    print("Putting Dave on the desktop (give him a few seconds to start)...")
    dave.start()
    time.sleep(5)                                 # start-up, fly-in, wave and his hello bubble

    print("Success: he listens, hears a command, then answers out loud...")
    dave.on_wake()
    time.sleep(2.5)
    dave.on_heard("open the browser")
    time.sleep(2)
    dave.on_done(True)
    speak("Done! I opened the browser.", "en")
    wait_until_quiet()
    time.sleep(1)

    print("Failure: he did not understand...")
    dave.on_wake()
    time.sleep(2)
    dave.on_heard("something unclear")
    time.sleep(1.5)
    dave.on_done(False)
    speak("Sorry, I did not understand that. Can you say it again?", "en")
    wait_until_quiet()
    time.sleep(1)

    print("Arabic: there is no Arabic voice yet, so he only shows the words...")
    speak("مرحبا، أنا ديف. كيف أساعدك؟", "ar")
    wait_until_quiet()

    input("Dave stays on your desktop. Try dragging him! Press Enter and watch him fly away...")
    dave.stop()


if __name__ == "__main__":
    main()