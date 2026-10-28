# llm.py — HEARSAY dialogue engine
# The game decides what is TRUE. Llama only decides how the NPC SAYS it.
# Runs a local Llama model through Ollama (http://localhost:11434), so it
# works offline and can later run on a Raspberry Pi 5.
# If no model is running, the game falls back to handwritten lines.
import json, os, random, re, threading, urllib.request

OLLAMA_URL = os.environ.get("HEARSAY_OLLAMA", "http://localhost:11434")
MODEL = os.environ.get("HEARSAY_MODEL", "llama3.2:1b")

WORLD = ("You are a character in HEARSAY, a 2D space game. The galaxy is built from "
         "rumors: places only exist because people talk about them. You live on a "
         "small station on the frontier. A lone pilot has just docked and is talking to you.")

PERSONALITY = {
    "scheming": "You are greedy and charming, always working an angle.",
    "nervous":  "You are jumpy and anxious, worried about pirates.",
    "chatty":   "You are lonely and warm, delighted to have company.",
    "calm":     "You are relaxed and matter-of-fact.",
}

INTENT = {
    "truth": "You honestly believe this and it is true. Say it plainly.",
    "lie": ("This is a LIE. You want the pilot to go there because {why}. Be convincing "
            "and friendly. Never admit you are lying."),
    "mistaken": ("You sincerely believe this. You heard it from {source}. You have no idea "
                 "it might be wrong."),
}

WHY = {"get_rich": "you plan to grab the real cache yourself while they're gone",
       "stay_safe": "you want pirates chasing them instead of you",
       "find_company": "you want them to come back and visit",
       "idle": "it amuses you"}

RULES = ("Reply with ONE or TWO short spoken sentences, under 30 words total. "
         "No quotation marks, no stage directions, no lists. Stay in character. "
         "Never mention being an AI or a game.")

# ---------------- handwritten fallbacks ----------------
FALLBACK_PITCH = {
    "scheming": ["Darling! A cache {dir}, {reward}cr and nobody's touched it. Lucky you.",
                 "Between us? There's {reward}cr sitting {dir}. Go before someone else does."],
    "nervous":  ["Th-there's a cache {dir}. {reward}cr. Just... watch for pirates, okay?",
                 "Heard of {reward}cr floating {dir}. I'm not going. You can, though."],
    "chatty":   ["Oh, a visitor! Did you hear? A cache {dir}, {reward}cr! Come back and tell me!",
                 "Finally someone to talk to! There's {reward}cr out {dir}, they say."],
    "calm":     ["There's a cache {dir}. About {reward}cr.",
                 "Word is {reward}cr is drifting {dir}. Your call."],
}
FALLBACK_SOURCE = {
    "self": ["Saw it with my own eyes. Would I lie to you?",
             "Nobody told me. I was there."],
    "other": ["Oh, {source} told me. Lovely soul.",
              "{source} mentioned it last shift. Seemed sure of it."],
}


class Dialogue:
    """Asks Llama for NPC lines on a background thread so the game never freezes."""

    def __init__(self):
        self.online = None          # None = still checking, True/False after
        self.results = {}           # request id -> text
        self.next_id = 0
        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        try:
            with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=2) as r:
                names = [m.get("name", "") for m in json.load(r).get("models", [])]
            self.online = any(n.split(":")[0] == MODEL.split(":")[0] for n in names)
        except Exception:
            self.online = False

    @property
    def status(self):
        if self.online is None: return "AI: checking..."
        return f"AI: {MODEL}" if self.online else "AI: offline (scripted lines)"

    # ---- public API ----
    def pitch(self, npc, claim, intent, direction):
        reward = int(claim.reward_claimed)
        fb = random.choice(FALLBACK_PITCH[npc.mood]).format(dir=direction, reward=reward)
        why = WHY.get(npc.goal, WHY["idle"])
        prompt = (f"{WORLD}\nYour name is {npc.name}. {PERSONALITY[npc.mood]}\n"
                  f"Right now you are thinking: {npc.thought}\n"
                  f"Tell the pilot about a supply cache to the {direction}, worth {reward} credits.\n"
                  f"{INTENT[intent].format(why=why, source=claim.heard_from)}\n{RULES}\n"
                  f"{npc.name}:")
        return self._ask(prompt, fb, must_contain=[direction.split("-")[0]])

    def source(self, npc, claim, intent):
        self_seen = claim.heard_from == "saw it myself"
        fb = random.choice(FALLBACK_SOURCE["self" if self_seen else "other"]).format(source=claim.heard_from)
        who = "you saw it yourself" if self_seen else f"{claim.heard_from} told you"
        extra = ("You are lying, so if pressed, be a little vague or change the subject. "
                 if intent == "lie" else "")
        prompt = (f"{WORLD}\nYour name is {npc.name}. {PERSONALITY[npc.mood]}\n"
                  f"The pilot asks: Where did you hear about that cache?\n"
                  f"Answer: {who}. {extra}{RULES}\n{npc.name}:")
        return self._ask(prompt, fb)

    def get(self, rid):
        return self.results.get(rid)

    # ---- internals ----
    def _ask(self, prompt, fallback, must_contain=()):
        rid = self.next_id; self.next_id += 1
        if not self.online:
            self.results[rid] = fallback
            return rid
        def work():
            text = fallback
            try:
                body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                                   "options": {"temperature": 0.8, "num_predict": 60}}).encode()
                req = urllib.request.Request(OLLAMA_URL + "/api/generate", body,
                                             {"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=25) as r:
                    out = clean(json.load(r).get("response", ""))
                # keep the game honest: the line must point the right way
                if out and all(w.lower() in out.lower() for w in must_contain):
                    text = out
            except Exception:
                pass
            self.results[rid] = text
        threading.Thread(target=work, daemon=True).start()
        return rid


def clean(t):
    t = t.strip().split("\n")[0]
    t = re.sub(r'^[A-Z][\w ]{0,20}:\s*', "", t)        # drop "Vex Marrow:" prefixes
    t = re.sub(r'\*[^*]*\*|\([^)]*\)', "", t)           # drop *actions* and (asides)
    t = t.replace('"', "").strip()
    parts = re.split(r'(?<=[.!?])\s+', t)
    t = " ".join(parts[:2])
    return t[:170]
