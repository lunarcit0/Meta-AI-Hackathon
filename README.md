# HEARSAY

A 2D space exploration game where the galaxy is built from rumors, and the people telling them might be lying.

The game engine decides what is true. A local Llama model decides how each character *says* it: charming, nervous, lonely, or scheming. Lies spread between NPCs and mutate as they travel, growing more confident, more rewarding, and more dangerous with every retelling.

## Run it (scripted dialogue, no AI needed)

You need Python 3.10 or newer.

```
pip install -r requirements.txt
python main.py
```

On Mac, use `pip3` and `python3` if `pip`/`python` don't work.

## Turn on the AI dialogue (Llama)

1. Install Ollama from https://ollama.com
2. Download Meta's small Llama model (about 1.3 GB):
   ```
   ollama pull llama3.2:1b
   ```
3. Start the game as usual. The top-right corner says `AI: llama3.2:1b` when it's connected.

Want a bigger model? `ollama pull llama3.2:3b`, then run with
`HEARSAY_MODEL=llama3.2:3b python main.py` (Mac/Linux) or
`set HEARSAY_MODEL=llama3.2:3b` then `python main.py` (Windows).

If the model isn't running, the game uses handwritten lines, so it never breaks during a demo.

## Controls

| Key | Action |
| --- | --- |
| W / ↑ | Thrust |
| A D / ← → | Turn |
| Space | Fire |
| E | Dock and talk / leave |
| 1 | "Where did you hear that?" |
| F1 | Truth debug view (shows the real cache and whether the NPC lied) |
| P | Save a screenshot |
| Esc | Quit |

## How it works

- `main.py` — the game: flying, combat, NPC minds, and the rumor system.
- `llm.py` — sends each NPC's personality, mood, and the engine's decision (truth, lie, or mistaken) to Llama, and gets back one or two lines. Runs in the background so the game never freezes. Lines that point the wrong direction are rejected, so the AI can't break the world's logic.

Built to run later on a Raspberry Pi 5 (8 GB) handheld.
