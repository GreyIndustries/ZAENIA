"""Load Talk when the server starts, so the first chat turn after a restart isn't a cold start (about 6 s)."""
from __future__ import annotations

import threading


def warm_talk() -> threading.Thread:
    def run() -> None:
        try:
            from core.brain.conductor import TALK_KEEP_ALIVE, TALK_MODEL
            from core.brain.local_llm import _game_keep_alive, set_residency
            if _game_keep_alive(TALK_KEEP_ALIVE) != TALK_KEEP_ALIVE:
                return  # a game is running; leave the graphics card to it
            set_residency(TALK_MODEL, TALK_KEEP_ALIVE)
            from core.brain.conversation_threads import embed_local
            embed_local(["warm"])
        except Exception:
            pass  # Ollama not running yet: the first turn loads Talk as before
    thread = threading.Thread(target=run, name="warm-talk", daemon=True)
    thread.start()
    return thread
