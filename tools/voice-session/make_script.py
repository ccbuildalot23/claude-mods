"""Render the reading script from the session plan. His lines come from the plan verbatim; only direction is added,
always in italics and brackets so it can never be mistaken for his words."""
import json, sys

plan = json.load(open(sys.argv[1], encoding="utf-8"))
OUT = sys.argv[2]

SETS = {
    1: ("Set 1: Warm light", "Love, tenderness, gratitude. Sit back. Talk to one person you love, like it's sunrise and you're on the couch. "
        "A half smile you can hear. Unhurried. About 4 minutes."),
    2: ("Set 2: Honest weight", "The heavy truths. Sit down for this one. Lower and slower than feels normal. Don't perform the pain, just "
        "tell it plainly; it's fine to sound tired. About 5 minutes."),
    3: ("Set 3: Faith and climbing", "Gratitude, growth, a little swagger. Stand up for this set, chest open, feet planted. The voice of "
        "someone who made it through. Steady pocket; your rapper's rhythm is welcome here. About 5 minutes."),
}

# passage id -> (mood/pace note, {line index after which to take a full breath})
D = {
 "S1-01": ("Warm-up, and the B side of your DP-F8 test. Gentle invitation. Let 'darkness' sit low, lift a little on 'light'. Slow.", {0}),
 "S1-02": ("Close and intimate, almost a murmur. 'Relax' is an exhale: let it fall like a sigh.", {1}),
 "S1-03": ("Quiet confidence, a promise. Land 'say' softly.", set()),
 "S1-04": ("Slow, and a little softer as you go.", set()),
 "S1-05": ("Intimacy building. Start hushed. Open up on 'unlink' (relief). A small proud smile on 'magnificence'. Slow right down for the last line.", {1, 3, 4}),
 "S1-06": ("A wry smile at your old self. A little lift on 'Crazy'.", set()),
 "S1-07": ("Storyteller, like telling a friend. Tiny pause after 'manned up,' and 'opened up,' then soften into 'finally let her in'.", {0}),
 "S1-08": ("Smooth and unhurried, like pouring a glass.", set()),
 "S1-09": ("Almost a chant. Equal weight on both lines.", {0}),
 "S1-10": ("Thoughtful. The dots are a real pause: count two.", {0}),
 "S1-11": ("Gentle. Pause at each set of dots. 'cure all' lands warm and sure.", {0, 1}),
 "S1-12": ("Savor it. Say 'every vowel' like you mean every one.", set()),
 "S1-13": ("Reflective, a soft smile. Small pause after 'roses'.", set()),
 "S1-14": ("Two short sentences with a pause between. 'Grapes turn to wine' slow and satisfied.", set()),
 "S1-15": ("Morning energy, a little wonder on 'amazement'.", set()),
 "S1-16": ("Soft and reassuring. Pause after 'too'.", {0}),
 "S1-17": ("Proud and welcoming. A touch of weight on 'crown'.", set()),
 "S1-18": ("Plain and kind. Warm on 'the people around me'.", set()),
 "S1-19": ("Calm, content. Pause after 'enough.' The second sentence lighter, almost dreamy.", set()),
 "S1-20": ("Direct and close, this is a brand line. Pause after 'heard.' Then 'I want to be felt' lower and slower.", set()),
 "S2-01": ("Your first voiced post (Mon Oct 26), so take your time. Tired honesty, then a flicker of resolve. First four lines slow and heavy. "
           "Let the first 'I don't know' trail off and hold two counts. Lift on 'But do have the energy' (first hope). "
           "'At this point even?' you're asking yourself. The last 'I don't know!' is sharper, frustrated, real.", {3, 4, 6}),
 "S2-02": ("From heavy to a vow. Steady and deliberate. 'instead of War' firm and short. Then open up: slow on 'front door'.", {1, 4}),
 "S2-03": ("An argument in your head: a bit quicker and tight on the first two lines, then slow on 'vs my heart and soul'.", {1}),
 "S2-04": ("Gravity, then gratitude. Pause at the dots. 'Now I Thank God' brighter.", {0}),
 "S2-05": ("A calm declaration. 'No more victim me' firm and slow; the rest flows like an explanation.", {0}),
 "S2-06": ("Hurt but controlled, a little cool. Let the last line land flat and slow.", {1}),
 "S2-07": ("A prayer, barely above a whisper. The second line even softer. (Say 'somewhere'; the spelling on screen stays yours.)", {0}),
 "S2-08": ("Dry humor. A small smile on 'savior', a wink on the last line.", set()),
 "S2-09": ("Vulnerable and slow. Pause after 'fear'. 'healing year' softly.", {0}),
 "S2-10": ("Low and close to the phone. Every word weighted.", set()),
 "S2-11": ("Honest with a twist: the stress, then a small lift on 'blessing'.", set()),
 "S2-12": ("Tight, held-in voice. Slow.", set()),
 "S2-13": ("Owning it, no self-pity. Quiet. Pause after 'heart.'", set()),
 "S2-14": ("One long breath of a sentence: breathe before you start. Gentle. '...and that's ok.' is a release.", set()),
 "S2-15": ("Clever and pointed. Pause after each line. 'Even phonetically' like a dry punchline.", {0, 1}),
 "S2-16": ("Gentle firmness, standing up for yourself.", {0}),
 "S3-01": ("Rhythmic. Let 'altar' and 'Altering' play off each other. Last line slow and earnest.", {1}),
 "S3-02": ("Ride the rhymes. Grateful on 'Thank God I survived'. Smile on the last line.", {1}),
 "S3-03": ("Easy confidence. 'No more abandoning ship' firm. 'I love learning who I am' warm and slower.", {2}),
 "S3-04": ("Your longest read, so think of it as a journey. Content (lines 1-2), momentum (3-4), clarity (5-7), worn out (8-10, slower), "
           "surrender (last two, soft).", {1, 3, 6, 9}),
 "S3-05": ("Measured and wise. A beat after 'On reality'. 'downgraded materialism' crisp.", {2}),
 "S3-06": ("Devotional and steady, building gently to 'heavenly seat'.", {1, 3}),
 "S3-07": ("Tender pride. 'Growing wings to fly' lifts.", {1}),
 "S3-08": ("Playful swagger with peace underneath. Grin on 'green bae' and 'cheddar'. Slower on 'But I left the rat race'. "
           "Proud on the Tortoise line. Grateful and slow at the end.", {2, 4, 7, 8}),
 "S3-09": ("A laugh in the second line, then sincere on 'Blessed things have turned around'.", {1}),
 "S3-10": ("Storyteller. 'fell down' low; 'Twenty twenty six' brighter; 'Super glued' with a proud smile.", {1}),
 "S3-11": ("Patient. Small pause at 'limited,'.", set()),
 "S3-12": ("Proud and deliberately unhurried (it's the tortoise).", set()),
 "S3-13": ("Tender, straight to the listener. Pause at the comma. This one is for them.", set()),
 "S3-14": ("Reverent. In the second sentence give each item its own space: closed hands... a wiser heart... tattooed pain... hard earned faith.", set()),
 "S3-15": ("Calm. Let us hear the breath between the two lines; that's the point of it.", {0}),
 "S3-16": ("Patient and humble. Slow on 'take time to build'.", set()),
 "S3-17": ("Swagger, a grin, the pocket. Have fun with it.", set()),
 "S3-18": ("Firm, clear, encouraging.", set()),
 "S3-19": ("Confident. Pause between the sentences; lean on 'vehicle'.", set()),
 "S3-20": ("Steady, like a coach who believes in you.", set()),
 "S3-21": ("Wise caution. Second line slower.", {0}),
}

def dates(p):
    ds = []
    for s in plan["slots"]:
        if s["voice"] in ("new", "ab-test") and any(f in p["fragments"] for f in s["fragments"]):
            ds.append("DP-F8 test" if s["date"] == "A/B" else s["date"][5:].replace("-", "/").lstrip("0"))
    return ", ".join(dict.fromkeys(ds))

def render_set(n):
    title, mood = SETS[n]
    out = [f"## {title}", f"_{mood}_", ""]
    for p in [p for p in plan["passages"] if p["set"] == n]:
        note, breaths = D[p["id"]]
        name = p["title"] if p["piece"] != "GEM" else "Gem"
        out.append(f"**{p['id'][3:]}. {name}** (posts {dates(p)})")
        out.append(f"_[{note}]_")
        for i, l in enumerate(p["lines"]):
            out.append(l + ("   _[breath]_" if i in breaths and i < len(p["lines"]) - 1 else ""))
        out.append("")
    return "\n".join(out)

assert set(D) == {p["id"] for p in plan["passages"]}, set(D) ^ {p["id"] for p in plan["passages"]}
for n in SETS:
    open(OUT.replace(".md", f"-set{n}.md"), "w", encoding="utf-8").write(render_set(n))
open(OUT, "w", encoding="utf-8").write("\n\n".join(render_set(n) for n in SETS))
print("ok")
