"""NXDOMAIN 결과 CSV에서 구매 수요가 있을 만한 도메인을 스코어링합니다.

기준:
- 숫자·자음 3연속·모음 과다/과소 패널티
- CVCV(자음-모음 교대) 등 발음 쉬운 패턴 가점
- 흔한 4글자 영단어·고유명사 가점
- 비속어·음가 불량 문자열 제외

사용 예:
    python recommend_domains.py result/com_4length_no_dns_list.csv --top 100
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from domain_checker_utils import RESULT_DIR, output_path

VOWELS = set("aeiou")
BAD_CHARS = set("qzxjkv")          # 희귀/발음 어려운 자음 (k,v는 경미)
BAD_SUBSTR = (                      # 비속어·불쾌 문자열
    "sex", "cum", "tit", "ass", "dck", "fuck", "shit", "puss",
    "nig", "fag", "kkk", "rape", "pedo", " nazi",
)
GOOD_BIGRAMS = {"oo", "ee", "ll", "ss", "tt", "nn", "mm", "zz", "ck", "ng", "sh", "ch", "th"}
BAD_BIGRAMS = {"qx", "qj", "zx", "xj", "jq", "vq", "fq", "pq", "bk", "dg", "kt", "pt", "pf"}

# 흔한 4글자 영단어/고유명사 - 도메인 수요가 높은 후보
COMMON_WORDS = set("""
able acid aged aide airy alan ally also amen ante apex aqua arch area aria arid army atom aunt
axe4baby back bail bait bake bald bale ball balm band bane bang bank barb bare bark barn base
bath bead beak beam bean bear beat beck beef been beer bell belt bend bent berg best beta bias
bike bile bill bind bird bite blabblah blah blob bloc bloc blot blow blue blur boar boat bode
body boil bold bolt bomb bond bone book boom boon boot bore born boss both bout bowl brag bran
brat bred brew brig brim brow buck bulb bulk bull bump bunk buoy burn burr bury bush bust busy
cafe cage cake calm came camp cane cape card care cart case cash cast cave cell cent chap char
chat chef chew chic chin chip chop city clad clam clan clap claw clay clef clip clod clog clop
club clue coal coat coax code coil coin coke cola cold colt comb come cone cook cool coop cope
copy cord core cork corn cost cove crab cram crew crib crop crow cube cult curb cure curl cusp
cute czar dale dame damn dare dark darn dart dash data date dawn daze dead deaf deal dean dear
debt deck deed deem deep deer deft deli demo dent deny desk dial dice diet dine ding dirt disc
dish disk diva dive dock does doll dome done doom door dose dote dove down doze drab drag draw
drip drop drum dual duck duct dude duel duet dull dump dune dusk dust duty each earn ease east
easel east easy echo edge edit eel8eggs else emit envy epic eras etch even ever evil exam exit
expo eyed face fact fade fail fair fake fall fame fang fare farm fast fate fawn fear feat feed
feel feet fell felt fern feud file fill film find fine fire firm fish fist five flag flak flap
flat flaw flea fled flee flew flex flip flit floe flog flop flow flub foam foal foil fold folk
fond font food fool foot ford fore fork form fort foul four fowl frag free frog from fuel full
fund funk furl fuse fuss fuzz gain gait gale gall game gang gate gave gaze gear geek geld gems
germ gift gild girl gist give glad glam glee glen glow glue goal goat goes gold golf gone gong
good gore gown grab gram gray grew grid grim grin grip grit grow grub gulf gush gust guts guys
hack hail hair half hall halo halt hand hang hard hare hark harm harp hash hate haul have hawk
haze head heal heap hear heat heed heel heir held hell helm help herb herd here hero hide hike
hill hint hire hiss hive hold hole holy home hone honk hood hoof hook hoop hope horn hose host
hour howl huff huge hulk hull hump hung hunt hurl hurt hush hymn iced icon idea idle idol inch
info inch into iris iron isle itch item jail jazz jean jeer jest jets join joke jolt jowl jump
junk jury just keel keen keep keno kept kick kill kiln kilo kind king kiss kite kiwi knee knew
knit knob knot lace lack lady laid lake lamb lame lamp land lane lard lark lash last late laud
lava lawn lazy leaf leak lean leap left lend lens lent less lest levy liar lick life lift like
lily limb lime line link lion list live load loaf loan lobby lobe lock loft logo lone long look
loom loop lord lore lose loss lost loud love luck lull lump lung lure lurk lush lust lute lynx
mace made mage mail main make male mall malt mane many mare mark mars mask mass mast mate math
maze mead meal mean meat meek meet mega meld melt memo mend menu meow mere mesh mess meta mice
midi mike mile milk mill mime mind mine mini mint mire miss mist mite moan moat mock mode mold
mole molt monk mood moon moor moot mope more morn moss most moth move much muff mule mull murk
muse mush musk must mute myth nail name nape navy near neat neck need nest news next nice nick
nine node none noon norm nose note noun nova nude nude null numb oath obey odds ogle ogre oils
okay omen omit once only onto onyx opal open oral orca oval oven over pace pack pact page paid
pail pain pair pale pall palm pane pang pant papa pare park part pass past path peak peal pear
peas peat peck peek peel peep peer pelt pend pens perk perm pert peso pest pick pier pile pill
pine ping pink pint pipe plan plat play plea pled plod plop plot plow plug plum plus poach poem
poet poke pole poll pond pone pony pool poor pope pore pork port pose post pour pout pray prep
prey prim prod prof prom prop prow pull pulp pump punk punt pure purr push puts quad quay quid
quip quit quiz race rack raft rage raid rail rain rake ramp rang rank rant rare rash rate rave
rays raze read real rear reck redo reed reef reek reel refs rein rely rend rent rest rice rich
ride rift rill rime ring rink riot ripe rise risk rite road roam roar robe rock rode role roll
romp roof rook room root rope rose rosy rote rout rove ruby rude ruin rule rump rune rung runt
rush rust ruth sack safe saga sage said sail sake sale salt same sand sane sang sank sash save
saw4scam seal seam sear seat sect seed seek seem seen seep seer self sell semi send sent sept
sera serf sexy shade shaft shake shale shall shame shape share shark sharp shave shawl shed shin
ship shirt shock shoe shop shot show shut sick side sift sigh sign silk sill silo silt sing sink
sire site size skew skid skim skin skip slab slam slap slat sled slew slid slim slip slit slob
slog slop slot slow slug slum slur smog smug smug snag snap snip snob snot snow snug soak soap
soar sock soda sofa soft soil sold sole solo soma some song sons soot sore sort soul soup sour
span spar spat sped spin spit spot spry spud spun spur stab stag star stay stem step stew stir
stop stow stub stud stun such suds sued suet suit sulk sumo sung sunk sure surf swab swag swam
swan swap sway swim swum tail take tale talk tall tame tank tape tarn tart task taut taxi teal
team tear tech teed teen tell temp tend tent term tern test text than that thaw them then they
thin this thou thru thud thug tick tide tidy tied tier tile till tilt time tine ting tint tiny
tips tire toad toil told toll tomb tone tong took tool toot tops tore torn tort toss tour tout
town trap tray tree trek trig trim trio trip trod trot troy true tsar tuba tube tuck tuft tuna
tune turf turn tusk tutu twig twin twit type tyre ugly undo unit unto upon urge urn5used used
user urge vast veil vein vent verb vest veto vibe vice view vine visa vise void vole volt vote
wade wage wait wake walk wall wand want ward ware warm warn warp wars wart wary wash wasp wave
wavy wax4ways weak weal wean wear webs weed week weep weft weld well welt were west what when
whim whip whir whit whiz whoa whom wick wide wife wild will wilt wily wind wine wing wink wipe
wire wise wish with wits wolf womb wont wood woof wool word wore work worm worn wort wove wrap
wren writ yard yarn yawl year yell yelp yoga yogh yoke yolk yore your zeal zero zest zinc zing
zone zoom
""".split())


def score_domain(name: str) -> float:
    """4글자 도메인의 구매 수요 점수 (높을수록 추천)."""
    if not name.isalpha() or len(name) != 4:
        return -1
    low = name.lower()
    if any(b in low for b in BAD_SUBSTR):
        return -1

    vowels = [c for c in low if c in VOWELS]
    score = 0.0

    # 모음 수: 2개가 이상적, 1개/4개는 감점
    nv = len(vowels)
    if nv == 2:
        score += 3
    elif nv == 1:
        score += 0.5
    elif nv == 3:
        score += 1
    else:
        return -1  # 모음 없음/4개 전부 -> 발음 불가

    # 자음 연속 검사
    max_run = 0
    run = 0
    prev_v = None
    for c in low:
        is_v = c in VOWELS
        if prev_v is not None and is_v == prev_v:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
        prev_v = is_v
    if max_run >= 2:      # 모음/자음 3연속
        return -1
    if max_run == 1:      # 2연속은 경미 감점
        score -= 1

    # CVCV 패턴 가점 (가장 브랜드성 높은 구조)
    pat = "".join("V" if c in VOWELS else "C" for c in low)
    if pat == "CVCV":
        score += 6
    elif pat in ("VCVC", "CVCV"[:0] + "CVCV"):
        score += 2
    elif pat in ("CVCC", "CCVC"):
        score -= 1

    # 이웃 글자 조합
    for i in range(3):
        bg = low[i:i+2]
        if bg in GOOD_BIGRAMS:
            score += 0.7
        if bg in BAD_BIGRAMS:
            score -= 2

    # 희귀 자음 페널티
    score -= sum(2 for c in low if c in BAD_CHARS)

    # 흔한 단어/이름
    if low in COMMON_WORDS:
        score += 8

    # 같은 글자 반복 (anna, otto 스타일) - 소폭 가감
    if len(set(low)) <= 3:
        score += 1.5
    if low[0] == low[3] or low[1] == low[2]:
        score += 1

    return score


def main():
    ap = argparse.ArgumentParser(description="미등록 도메인 구매 수요 스코어링")
    ap.add_argument("csv", help="NXDOMAIN 결과 CSV (domain,status 형식)")
    ap.add_argument("--top", type=int, default=100, help="상위 출력 개수")
    ap.add_argument("--out", default=None, help="결과 CSV 경로 (생략 시 result/ 자동)")
    args = ap.parse_args()

    scored = []
    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            d = (row.get("domain") or "").strip().lower()
            name = d[:-4] if d.endswith(".com") else d
            s = score_domain(name)
            if s >= 0:
                scored.append((s, d))

    scored.sort(key=lambda x: -x[0])
    out_path = args.out or output_path("domain_recommendations")
    os.makedirs(RESULT_DIR, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["rank", "score", "domain"])
        for i, (s, d) in enumerate(scored[: args.top * 5], 1):
            w.writerow([i, f"{s:.1f}", d])

    print(f"채점 통과: {len(scored):,}개 / 전체 후보 중 상위 {min(len(scored), args.top)}개 출력")
    print(f"저장: {out_path}\n")
    for i, (s, d) in enumerate(scored[: args.top], 1):
        print(f"{i:3d}. {d:15s} ({s:.1f})")


if __name__ == "__main__":
    main()
