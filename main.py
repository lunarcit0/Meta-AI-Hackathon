# main.py — HEARSAY v0.3
# Internal: 480x270 (chunky pixel) scaled x2 to 960x540 — Pi/mobile friendly
# Controls: WASD/Arrows fly | SPACE fire | E dock/talk/leave | 1 ask source
#           F1 truth-debug | P save screenshot | ESC quit
import pygame, math, random, sys
from dataclasses import dataclass, field
from llm import Dialogue

IW, IH, SCALE = 480, 270, 2
WORLD = 4000
INK = (15, 12, 20)

PALETTE = {
    "skin":  [(242,140,40),(46,196,182),(155,140,242),(120,200,90),(242,194,48),(240,110,160)],
    "hair":  [(180,40,40),(20,160,140),(240,180,40),(160,120,220),(30,30,40),(240,240,230)],
    "accent":[(240,80,140),(250,200,40),(80,200,120),(80,140,250)],
}

# ---------------- Rumors that mutate ----------------
@dataclass
class Belief:
    topic: str
    claimed_pos: pygame.Vector2
    confidence: float = 0.6
    heard_from: str = "saw it myself"
    reward_claimed: float = 100
    danger: int = 0
    times_told: int = 0

    def retell(self, teller_name):
        drift = 180 * self.times_told
        return Belief(
            self.topic,
            self.claimed_pos + pygame.Vector2(random.uniform(-drift, drift),
                                              random.uniform(-drift, drift)),
            min(1.0, self.confidence + 0.1),          # surer every time!
            teller_name,
            self.reward_claimed * 1.5,                # prize inflates...
            self.danger + 1,                          # ...ambush grows too
            self.times_told + 1)

# ---------------- NPC minds ----------------
@dataclass
class PortraitDNA:
    skin: tuple; hair: tuple; feat_l: str; feat_r: str

@dataclass
class NPC:
    name: str; pos: pygame.Vector2; dna: PortraitDNA
    greed: float; fear: float; loneliness: float; honesty: float
    mood: str = "calm"; thought: str = "..."; goal: str = "idle"
    beliefs: dict = field(default_factory=dict)
    is_station: bool = True
    hear: object = None                               # version of the rumor they'll gossip

    def think(self):
        drive = max([("greed", self.greed), ("fear", self.fear),
                     ("loneliness", self.loneliness), ("rest", random.random()*0.3)],
                    key=lambda x: x[1])[0]
        self.mood, self.thought, self.goal = {
            "greed":      ("scheming", "That cache should be mine...", "get_rich"),
            "fear":       ("nervous",  "Too many pirates lately...", "stay_safe"),
            "loneliness": ("chatty",   "Hope someone docks soon...", "find_company"),
            "rest":       ("calm",     "Quiet shift today.", "idle")}[drive]

    def decide(self, topic, true_pos):
        b = self.beliefs.get(topic)
        if b and b.claimed_pos.distance_to(true_pos) > 120 and b.confidence > 0.5:
            return b, "mistaken"                       # sincerely wrong
        if self.goal in ("get_rich", "stay_safe") and (self.greed + self.fear)/2 > self.honesty:
            lie = Belief(topic, pygame.Vector2(-true_pos.x, true_pos.y),
                         0.9, "saw it myself", 100 * (1 + random.random()), 1, 1)
            return lie, "lie"                          # knowingly lying, politely
        return Belief(topic, true_pos.copy(), 0.8, "saw it myself", 100, 0, 0), "truth"

def make_cast(true_pos):
    npcs = [
        NPC("Vex Marrow", pygame.Vector2(400,-300),
            PortraitDNA(PALETTE["skin"][0], PALETTE["hair"][3], "brown_eye", "blue_eye"),
            greed=.9, fear=.2, loneliness=.3, honesty=.3),
        NPC("Mira Sol", pygame.Vector2(-900, 500),
            PortraitDNA(PALETTE["skin"][1], PALETTE["hair"][2], "mesh_eye", "mesh_eye"),
            greed=.2, fear=.3, loneliness=.95, honesty=.8, is_station=False),
        NPC("Odo Fen", pygame.Vector2(1000, 800),
            PortraitDNA(PALETTE["skin"][2], PALETTE["hair"][5], "tired_eye", "tired_eye"),
            greed=.3, fear=.9, loneliness=.4, honesty=.5),
    ]
    # Seed one false belief so Mira can amplify it
    npcs[1].beliefs["cache"] = Belief("cache", pygame.Vector2(-true_pos.x, true_pos.y), .7, "Vex Marrow")
    for n in npcs: n.think()
    return npcs

def compass(frm, to):
    """8-way direction on screen (up = north)."""
    d = to - frm
    ang = math.degrees(math.atan2(-d.y, d.x))
    names = ["east","north-east","north","north-west","west","south-west","south","south-east"]
    return names[round(ang / 45) % 8]

def wrap(font, text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= width: cur = test
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

# ---------------- Combat ----------------
@dataclass
class Pirate:
    pos: pygame.Vector2; hull: int = 30; tier: int = 1; fire_cd: float = 0.0
    vel: pygame.Vector2 = field(default_factory=pygame.Vector2)

def draw_portrait(s, dna, x, y, mood):
    pygame.draw.rect(s, dna.skin, (x, y, 48, 48)); pygame.draw.rect(s, INK, (x, y, 48, 48), 2)
    pygame.draw.rect(s, dna.hair, (x, y, 48, 10))                       # hair band
    for ex, feat in [(x+13, dna.feat_l), (x+35, dna.feat_r)]:           # asymmetric eyes
        if feat == "mesh_eye":
            pygame.draw.rect(s, (240,240,240), (ex-6, y+18, 12, 8)); pygame.draw.rect(s, INK, (ex-6, y+18, 12, 8), 1)
        elif feat == "flower_eyes":
            for a in range(5):
                pygame.draw.circle(s, (240,80,140), (ex+int(5*math.cos(a*1.26)), y+22+int(5*math.sin(a*1.26))), 3)
            pygame.draw.circle(s, (250,200,40), (ex, y+22), 2)
        else:
            col = (90,50,20) if feat == "brown_eye" else (80,140,250) if feat == "blue_eye" else INK
            pygame.draw.circle(s, (255,255,255), (ex, y+22), 5); pygame.draw.circle(s, col, (ex, y+22), 3)
    # everyone smiles. everyone.
    pygame.draw.arc(s, INK, (x+14, y+30, 20, 12), math.pi, 2*math.pi, 2)

# ---------------- Game ----------------
STAR_W, STAR_H = IW + 40, IH + 40

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((IW*SCALE, IH*SCALE))
        pygame.display.set_caption("Hearsay v0.3")
        self.canvas = pygame.Surface((IW, IH))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 8); self.big = pygame.font.SysFont("monospace", 11, bold=True)
        self.ai = Dialogue()
        self.ship = pygame.Vector2(0,0); self.vel = pygame.Vector2(); self.angle = -90
        self.true_cache = pygame.Vector2(1400,-1000)
        self.npcs = make_cast(self.true_cache)
        self.state = "FLYING"; self.current_npc = None; self.current_claim = None; self.current_intent = ""
        self.hull, self.shield, self.credits = 100, 50, 0
        self.shield_timer, self.fire_cd, self.gossip_timer, self.think_timer = 0, 0, 0, 0
        self.bullets, self.e_bullets, self.pirates = [], [], []
        self.msg, self.msg_t, self.debug, self.shot_n = "", 0, False, 0
        self.stars = [(random.uniform(0,STAR_W), random.uniform(0,STAR_H), random.choice([.3,.6,1.])) for _ in range(160)]
        self.claim_ambushed, self.real_known = False, False
        self.line_id, self.asked_source, self.t = None, False, 0.0

    def to_screen(self, w): return w - self.ship + pygame.Vector2(IW//2, IH//2)
    def show(self, t, s=3.5): self.msg, self.msg_t = t, s
    def screenshot(self):
        self.shot_n += 1
        pygame.image.save(self.screen, f"screenshot_{self.shot_n:03d}.png")
        self.show(f"Saved screenshot_{self.shot_n:03d}.png")

    def nearest_npc(self):
        for n in self.npcs:
            if self.ship.distance_to(n.pos) < 60: return n

    # ---- talking ----
    def start_talk(self, npc):
        self.vel *= 0
        self.current_npc, self.state = npc, "DOCKED"
        claim, intent = npc.decide("cache", self.true_cache)
        self.current_claim, self.current_intent = claim, intent
        self.claim_ambushed, self.asked_source = False, False
        npc.hear = claim   # they may gossip this version onward
        self.line_id = self.ai.pitch(npc, claim, intent, compass(npc.pos, claim.claimed_pos))

    def ask_source(self):
        if self.asked_source: return
        self.asked_source = True
        self.line_id = self.ai.source(self.current_npc, self.current_claim, self.current_intent)

    def leave(self):
        self.state = "FLYING"
        self.show("Rumor logged. Follow the '?' — if you trust them.")

    def gossip(self):
        """NPCs talk to each other off-screen. Lies spread + mutate."""
        src = random.choice(self.npcs); dst = random.choice(self.npcs)
        b = src.hear or src.beliefs.get("cache")
        if b and src is not dst:
            dst.beliefs["cache"] = b.retell(src.name)
            dst.hear = dst.beliefs["cache"]

    def spawn_ambush(self, center, danger):
        for i in range(1 + danger):
            p = center + pygame.Vector2(random.uniform(-160,160), random.uniform(-160,160))
            self.pirates.append(Pirate(p, 20 + 15*danger, danger))
        why = "they lied to you!" if self.current_intent == "lie" else "the rumor was wrong!"
        self.show(f"AMBUSH! {1+danger} pirates — {why}")

    def found_cache(self):
        self.credits += 100
        self.true_cache = pygame.Vector2(random.uniform(-2500,2500), random.uniform(-2500,2500))
        self.current_claim, self.real_known = None, False
        for n in self.npcs: n.beliefs.pop("cache", None); n.hear = None
        self.show("Real cache! +100cr ... new whispers on the wire.")

    def update(self, dt):
        keys = pygame.key.get_pressed()
        self.t += dt
        self.think_timer += dt; self.gossip_timer += dt
        if self.think_timer > 10: self.think_timer = 0; [n.think() for n in self.npcs]
        if self.gossip_timer > 20: self.gossip_timer = 0; self.gossip()

        if self.state == "FLYING":
            if keys[pygame.K_a] or keys[pygame.K_LEFT]: self.angle -= 180*dt
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.angle += 180*dt
            rad = math.radians(self.angle)
            if keys[pygame.K_w] or keys[pygame.K_UP]: self.vel += pygame.Vector2(math.cos(rad), math.sin(rad))*260*dt
            self.vel *= .99; self.ship += self.vel*dt
            self.ship.x = max(-WORLD, min(WORLD, self.ship.x)); self.ship.y = max(-WORLD, min(WORLD, self.ship.y))

            self.fire_cd -= dt
            if keys[pygame.K_SPACE] and self.fire_cd <= 0:
                self.fire_cd = .22
                self.bullets.append([self.ship.copy(), pygame.Vector2(math.cos(rad), math.sin(rad))*420, 2.])

            c = self.current_claim
            if self.ship.distance_to(self.true_cache) < 45:
                self.found_cache()
            elif c and not self.claim_ambushed and c.danger > 0 and self.ship.distance_to(c.claimed_pos) < 45:
                self.claim_ambushed = True; self.spawn_ambush(c.claimed_pos, c.danger)

        # bullets
        for b in self.bullets[:]:
            b[0] += b[1]*dt; b[2] -= dt
            if b[2] <= 0: self.bullets.remove(b); continue
            for p in self.pirates[:]:
                if b[0].distance_to(p.pos) < 14:
                    p.hull -= 15; self.bullets.remove(b)
                    if p.hull <= 0:
                        self.pirates.remove(p); self.credits += 25
                        if not self.real_known and random.random() < .35:
                            self.real_known = True
                            self.show("Pirate down +25cr — his logs show the REAL cache!")
                        else:
                            self.show("Pirate down +25cr")
                    break
        # pirates
        for p in self.pirates:
            d = self.ship - p.pos; dist = max(d.length(), 1); d = d / dist
            want = d*70 if dist > 180 else -d*40 + pygame.Vector2(-d.y, d.x)*60
            p.vel += (want - p.vel)*dt*2; p.pos += p.vel*dt
            p.fire_cd -= dt
            if p.fire_cd <= 0 and dist < 260:
                p.fire_cd = 1.6; self.e_bullets.append([p.pos.copy(), d*240, 2.5])
        for b in self.e_bullets[:]:
            b[0] += b[1]*dt; b[2] -= dt
            if b[2] <= 0: self.e_bullets.remove(b); continue
            if b[0].distance_to(self.ship) < 12:
                self.e_bullets.remove(b); self.shield_timer = 0
                dmg = 8
                if self.shield > 0: self.shield = max(0, self.shield-dmg)
                else: self.hull -= dmg
                if self.hull <= 0:
                    self.hull, self.shield, self.ship, self.pirates = 100, 50, pygame.Vector2(), []
                    self.e_bullets.clear(); self.vel *= 0
                    self.credits = max(0, self.credits-50); self.show("Ship lost! Towed home -50cr")
                    break
        self.shield_timer += dt
        if self.shield_timer > 5: self.shield = min(50, self.shield + 12*dt)
        if self.msg_t > 0: self.msg_t -= dt

    def draw_marker(self, s, pos, col, label):
        sp = self.to_screen(pos)
        if -30 < sp.x < IW+30 and -30 < sp.y < IH+30:
            pygame.draw.circle(s, col, sp, 8, 2); s.blit(self.font.render(label, True, col), sp+(-len(label)*2, 10))
        else:  # edge arrow pointing toward it
            c = pygame.Vector2(IW//2, IH//2); d = (sp - c)
            if d.length() > 0:
                d.scale_to_length(min(IW, IH)//2 - 14)
                pygame.draw.circle(s, col, c + d, 3)

    def draw(self):
        s = self.canvas; s.fill((5,6,18))
        # parallax starfield that wraps forever
        for x,y,p in self.stars:
            sx = (x - self.ship.x*p) % STAR_W - 20; sy = (y - self.ship.y*p) % STAR_H - 20
            if 0 <= sx < IW and 0 <= sy < IH:
                c = int(120+100*p); s.set_at((int(sx),int(sy)), (c,c,min(255,c+30)))
        # truth stays hidden unless debug, or a pirate's logs revealed it
        if self.debug or self.real_known:
            self.draw_marker(s, self.true_cache, (80,255,160), "CACHE")
        if self.current_claim:
            self.draw_marker(s, self.current_claim.claimed_pos, (255,120,120), "?")
        # NPCs
        for n in self.npcs:
            sp = self.to_screen(n.pos)
            if -60 < sp.x < IW+60 and -60 < sp.y < IH+60:
                if n.is_station: pygame.draw.circle(s,(140,180,255),sp,22,2)
                else: pygame.draw.polygon(s,(200,160,255),[sp+(0,-10),sp+(8,8),sp+(-8,8)])
                s.blit(self.font.render(n.name.upper(),True,(180,210,255)), sp+(-22,26))
                # thought bubble — mood only, never honesty
                t = self.font.render(n.thought, True, INK); bw = t.get_width() + 6
                pygame.draw.rect(s,(240,240,235),(sp.x-bw//2, sp.y-42, bw, 12))
                s.blit(t,(sp.x-bw//2+3, sp.y-40))
                if self.state=="FLYING" and self.ship.distance_to(n.pos)<60:
                    s.blit(self.font.render("[E] Dock/Talk",True,(255,255,200)), sp+(-22,-56))
        # pirates + bullets
        for p in self.pirates:
            sp = self.to_screen(p.pos); pygame.draw.polygon(s,(255,80,80),[sp+(0,-9),sp+(7,7),sp+(-7,7)])
            pygame.draw.rect(s,(255,80,80),(sp.x-8,sp.y-14,max(0,p.hull)/3,2))
        for b in self.bullets: pygame.draw.circle(s,(255,240,150), self.to_screen(b[0]), 2)
        for b in self.e_bullets: pygame.draw.circle(s,(255,100,100), self.to_screen(b[0]), 2)
        # ship
        rad,c = math.radians(self.angle), pygame.Vector2(IW//2, IH//2)
        pts=[c+pygame.Vector2(math.cos(rad+a),math.sin(rad+a))*r for a,r in [(0,9),(2.5,6),(math.pi,4),(-2.5,6)]]
        pygame.draw.polygon(s,(255,220,120),pts); pygame.draw.polygon(s,INK,pts,1)
        # HUD
        s.blit(self.font.render(f"Cr:{self.credits}  Hull:{int(self.hull)}  Shield:{int(self.shield)}  Pirates:{len(self.pirates)}",True,(230,230,230)),(6,5))
        ai = self.font.render(self.ai.status, True, (130,200,150) if self.ai.online else (150,130,130))
        s.blit(ai, (IW - ai.get_width() - 6, 5))
        s.blit(self.font.render("WASD fly SPACE fire E talk F1 debug P screenshot",True,(130,130,150)),(6,IH-12))
        if self.msg_t>0:
            m = self.big.render(self.msg[:62],True,(255,240,180)); s.blit(m,(IW//2-m.get_width()//2,22))
        if self.debug and self.current_claim:
            c=self.current_claim
            s.blit(self.font.render(f"DEBUG intent={self.current_intent} danger={c.danger} told={c.times_told} reward={int(c.reward_claimed)} from={c.heard_from}",True,(255,90,90)),(6,16))
        if self.state=="DOCKED" and self.current_npc:
            self.draw_dialogue(s)
        self.screen.blit(pygame.transform.scale(s,(IW*SCALE,IH*SCALE)),(0,0))
        pygame.display.flip()

    def draw_dialogue(self, s):
        n = self.current_npc
        pygame.draw.rect(s,(10,12,30),(20,IH-92,IW-40,82)); pygame.draw.rect(s,(140,180,255),(20,IH-92,IW-40,82),2)
        draw_portrait(s,n.dna,30,IH-82,n.mood)
        x, y = 86, IH-84
        s.blit(self.font.render(n.name.upper(), True, (180,210,255)), (x, y)); y += 12
        text = self.ai.get(self.line_id)
        if text is None:
            text = "." * (1 + int(self.t*3) % 3)            # NPC is thinking
        for l in wrap(self.font, text, IW - 40 - (x - 20) - 10)[:4]:
            s.blit(self.font.render(l, True, (235,235,235)), (x, y)); y += 11
        opts = "[E] Leave" if self.asked_source else "[1] Where did you hear that?   [E] Leave"
        s.blit(self.font.render(opts, True, (255,255,200)), (x, IH-22))

    def run(self):
        while True:
            dt=min(self.clock.tick(60)/1000,.05)
            for e in pygame.event.get():
                if e.type==pygame.QUIT: pygame.quit(); sys.exit()
                if e.type==pygame.KEYDOWN:
                    if e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                    if e.key==pygame.K_F1: self.debug=not self.debug
                    if e.key==pygame.K_p: self.screenshot()
                    if e.key==pygame.K_e:
                        if self.state=="DOCKED": self.leave()
                        else:
                            n = self.nearest_npc()
                            if n: self.start_talk(n)
                    if e.key==pygame.K_1 and self.state=="DOCKED": self.ask_source()
            self.update(dt); self.draw()

if __name__=="__main__": Game().run()
