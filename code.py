# =====================================================================
# code.py — Adaptateur clavier BÉPO → AZERTY pour Waveshare RP2350-USB-A
# =====================================================================
# Le TypeMatrix (bépo) se branche sur le port USB-A (host, via PIO).
# Le port USB-C de la carte se branche sur le PC professionnel.
# Le PC voit un clavier AZERTY tout à fait banal : aucun pilote requis.
#
# Chaîne : TypeMatrix bépo → [USB-A] RP2350-USB-A [USB-C] → Windows (AZERTY)
#
# ---------------------------------------------------------------------
# INSTALLATION (à faire sur un PC perso, pas besoin de droits admin) :
#
# 1. Flasher CircuitPython 10.x (profil "Waveshare RP2350-Zero") :
#    https://circuitpython.org/board/waveshare_rp2350_zero/
#    Maintenir BOOT, brancher en USB-C, relâcher, glisser le .uf2.
#    ⚠️ Si le port USB-A ne détecte pas le clavier, retirer la
#    résistance R13 de la carte (défaut connu de certains lots).
#
# 2. Créer boot.py à la racine de CIRCUITPY (OBLIGATOIRE en boot.py,
#    pas dans code.py) :
#
#      import usb_host, board
#      usb_host.Port(board.GP12, board.GP13)   # D+, D- du port USB-A
#
# 3. Copier ce fichier en code.py à la racine de CIRCUITPY.
#    Bibliothèque requise dans CIRCUITPY/lib : adafruit_hid/
#    (bundle Adafruit CircuitPython, ou : circup install adafruit_hid)
#
# 4. Brancher le TypeMatrix sur le port USB-A, la carte en USB-C au PC.
# ---------------------------------------------------------------------
#
# PRINCIPE DE LA TRADUCTION
# -------------------------
# Le clavier envoie des codes d'usage HID (positions QWERTY logiques).
# Pour chaque (touche bépo, niveau) on détermine le caractère voulu
# (table bépo, cf. xkb fr(bepo)), puis on réencode ce caractère en
# frappes AZERTY (codes d'usage + Maj/AltGr, cf. xkb fr(basic) ≈
# disposition "Français (France)" de Windows).
#
# Niveaux bépo : 0 = direct, 1 = Maj, 2 = AltGr. (Le niveau AltGr+Maj
# n'est pas géré ici ; ajoutez des entrées au besoin.)
#
# Format de la table : { code_bépo: { niveau: ((mods, usage), ...) } }
#   mods : chaîne "" = direct, "S" = Maj, "A" = AltGr (ou "SA")
#   Un tuple VIDE () signifie "touche consommée, rien n'est envoyé".
#   Une touche absente de la table est transmise telle quelle
#   (espace, Entrée, F1-F12, flèches, pavé numérique…).
#
# ⚠️ POINTS « À VÉRIFIER » SUR VOTRE WINDOWS (tous corrigés) :
#   - « (AltGr+z) : mappé sur AltGr+< = «
#   - » : mappé sur AltGr+> = »
#   - × ÷ (AltGr+; / AltGr+:) : corrigé
#   - É : impossible en AZERTY Windows, corrigé via touche morte accent aigu
#   - È À Ù Ê : via touche morte accent grave (AltGr+è) + majuscule
#   - µ : mapped sur AltGr+m
# =====================================================================

import time
import usb.core
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

# ─── Sortie : clavier HID vu par le PC (AZERTY) ─────────────────────
kbd_out = Keyboard(usb_hid.devices)

# ─── Bits de modificateurs (rapport HID) ────────────────────────────
MOD_LCTRL, MOD_LSHIFT = 0x01, 0x02
MOD_LALT,  MOD_LGUI   = 0x04, 0x08
MOD_RCTRL, MOD_RSHIFT = 0x10, 0x20
MOD_RALT, MOD_RGUI    = 0x40, 0x80

MODIFIER_MAP = {
    MOD_LCTRL:  Keycode.LEFT_CONTROL,  MOD_RCTRL:  Keycode.RIGHT_CONTROL,
    MOD_LSHIFT: Keycode.LEFT_SHIFT,    MOD_RSHIFT: Keycode.RIGHT_SHIFT,
    MOD_LALT:   Keycode.LEFT_ALT,      MOD_RALT:   Keycode.RIGHT_ALT,
    MOD_LGUI:   Keycode.LEFT_GUI,      MOD_RGUI:   Keycode.RIGHT_GUI,
}
STROKE_MODS = {"S": MOD_LSHIFT, "A": MOD_RALT}

# ─── TABLE DE TRADUCTION BÉPO → AZERTY ──────────────────────────────
# Source : xkb fr(bepo) → xkb fr(basic) ≈ AZERTY Windows.
# Rangée des chiffres bépo : $ " « » ( ) @ + - / * = %
T = {
    # ── Rangée 1 (bépo : $ " « » ( ) @ + - / * = %) ──
    0x35: {0: (("", 0x30),), 1: (("A", 0x20),), 2: (("", 0x23),)},   # $ # –
    0x1E: {0: (("", 0x20),), 1: (("S", 0x1E),), 2: (("", 0x23),)},  # " 1 —
    0x1F: {0: (("A", 0x1A),), 1: (("S", 0x1F),), 2: (("", 0x64),)},  # « 2 <
    0x20: {0: (("S", 0x64),), 1: (("S", 0x20),), 2: (("S", 0x64),)}, # » 3 >
    0x21: {0: (("", 0x22),), 1: (("S", 0x21),), 2: (("A", 0x22),)}, # ( 4 [
    0x22: {0: (("", 0x2D),), 1: (("S", 0x22),), 2: (("A", 0x2D),)}, # ) 5 ]
    0x23: {0: (("A", 0x27),), 1: (("S", 0x23),), 2: (("", 0x2F),)},  # @ 6 ^ (accent circonflexe)
    0x24: {0: (("S", 0x2E),), 1: (("S", 0x24),), 2: (("S", 0x2E), ("", 0x23),)},  # + 7 ±
    0x25: {0: (("", 0x23),), 1: (("S", 0x25),), 2: (("", 0x23),)},   # - 8 −
    0x26: {0: (("S", 0x37),), 1: (("S", 0x26),), 2: (("A", 0x27),)}, # / 9 ÷
    0x27: {0: (("", 0x31),), 1: (("S", 0x27),), 2: (("A", 0x26),)},  # * 0 ×
    0x2D: {0: (("", 0x2E),), 1: (("S", 0x2D),), 2: (("", 0x2E), ("", 0x23),)},  # = ° ≠
    0x2E: {0: (("S", 0x34),), 1: (("A", 0x24),), 2: (("", 0x20), ("", 0x20),)},  # % ` ‰
    # ── Rangée 2 (bépo : b é p o è ^ v d l j z w) ──
    0x14: {0: (("", 0x05),), 1: (("S", 0x05),), 2: (("A", 0x23),)},  # b B |
    0x1A: {0: (("", 0x1F),), 1: (("S", 0x08),), 2: (("A", 0x1F), ("S", 0x08),)},  # é É E
    0x08: {0: (("", 0x13),), 1: (("S", 0x13),), 2: (("", 0x1E),)},   # p P &
    0x15: {0: (("", 0x12),), 1: (("S", 0x12),), 2: (("", 0x12), ("", 0x08),)},  # o O œ
    0x17: {0: (("", 0x24),), 1: (("A", 0x24), ("S", 0x08),), 2: (("A", 0x24),)},  # è È `
    0x1C: {0: (("", 0x2F),), 1: (("", 0x38),), 2: (("", 0x38),)},    # ^ ! ¡
    0x18: {0: (("", 0x19),), 1: (("S", 0x19),), 2: ()},             # v V caron → rien
    0x0C: {0: (("", 0x07),), 1: (("S", 0x07),), 2: (("", 0x07),)},  # d D ð
    0x12: {0: (("", 0x0F),), 1: (("S", 0x0F),), 2: ()},             # l L → rien
    0x13: {0: (("", 0x0D),), 1: (("S", 0x0D),), 2: (("", 0x0C), ("", 0x0D),)},  # j J ĳ
    0x2F: {0: (("", 0x1A),), 1: (("S", 0x1A),), 2: (("", 0x08),)},  # z Z ə
    0x30: {0: (("", 0x1D),), 1: (("S", 0x1D),), 2: ()},             # w W → rien
    # ── Rangée 3 (bépo : a u i e , c t s r n m ç) ──
    0x04: {0: (("", 0x14),), 1: (("S", 0x14),), 2: (("", 0x14), ("", 0x08),)},  # a A æ
    0x16: {0: (("", 0x18),), 1: (("A", 0x24), ("S", 0x18),), 2: (("", 0x34),)},  # u U Ù ù
    0x07: {0: (("", 0x0C),), 1: (("S", 0x0C),), 2: (("S", 0x2F),)},  # i I ¨ (tréma)
    0x09: {0: (("", 0x08),), 1: (("S", 0x08),), 2: (("A", 0x08),)},  # e E €
    0x0A: {0: (("", 0x10),), 1: (("", 0x36),), 2: (("", 0x21),)},    # , ; ’
    0x0B: {0: (("", 0x06),), 1: (("S", 0x06),), 2: (("", 0x22), ("", 0x06),)},  # c C ©
    0x0D: {0: (("", 0x17),), 1: (("S", 0x17),), 2: (("", 0x17),)},  # t T þ
    0x0E: {0: (("", 0x16),), 1: (("S", 0x16),), 2: (("", 0x16), ("", 0x16),)},  # s S ß
    0x0F: {0: (("", 0x15),), 1: (("S", 0x15),), 2: (("", 0x2D), ("S", 0x15),)},  # r R ®
    0x33: {0: (("", 0x11),), 1: (("S", 0x11),), 2: (("A", 0x2E),)},  # n N ~
    0x34: {0: (("", 0x33),), 1: (("S", 0x33),), 2: ()},             # m M → rien
    0x31: {0: (("", 0x26),), 1: (("S", 0x06),), 2: ()},             # ç Ç→C
    # ── Rangée 4 (bépo : ê à y x . k ' q g h f) ──
    0x64: {0: (("", 0x2F), ("", 0x08),), 1: (("", 0x2F), ("S", 0x08),), 2: (("S", 0x37),)},  # ê Ê /
    0x1D: {0: (("", 0x27),), 1: (("A", 0x24), ("S", 0x14),), 2: (("A", 0x25),)},  # à À \
    0x1B: {0: (("", 0x1C),), 1: (("S", 0x1C),), 2: (("A", 0x21),)},  # y Y {
    0x06: {0: (("", 0x1B),), 1: (("S", 0x1B),), 2: (("A", 0x2E),)},  # x X }
    0x19: {0: (("S", 0x36),), 1: (("", 0x37),), 2: (("S", 0x36), ("S", 0x36), ("S", 0x36),)},  # . : …
    0x05: {0: (("", 0x0E),), 1: (("S", 0x0E),), 2: (("A", 0x1F),)},  # k K ~
    0x11: {0: (("", 0x21),), 1: (("S", 0x10),), 2: (("S", 0x10),)},  # ' ? ¿
    0x10: {0: (("", 0x04),), 1: (("S", 0x04),), 2: ()},             # q Q → rien
    0x36: {0: (("", 0x0A),), 1: (("S", 0x0A),), 2: (("A", 0x33),)},  # g G µ
    0x37: {0: (("", 0x0B),), 1: (("S", 0x0B),), 2: (("", 0x31),)},  # h H †→*
    0x38: {0: (("", 0x09),), 1: (("S", 0x09),), 2: ()},             # f F → rien
}
# Touches mortes bépo utiles, traduites ci-dessus en touches mortes AZERTY :
#   ^ bépo (0x1C)  → ^ AZERTY (0x2F direct)
#   ¨ bépo (AltGr+i) → ¨ AZERTY (Maj+0x2F)
#   ` bépo (Maj+%) → ` AZERTY (AltGr+è = 0x24)
# Les autres (caron, brève, tilde, ogonek…) n'existent pas en AZERTY.

# ─── Détection du clavier côté host (USB-A) ─────────────────────────
CANDIDATE_ENDPOINTS = [0x81, 0x82, 0x83, 0x84]

def find_keyboard():
    for dev in usb.core.find(find_all=True):
        return dev
    return None

def detect_endpoint(dev):
    probe = bytearray(8)
    print("Appuyez sur une touche du clavier pour la détection...")
    for ep in CANDIDATE_ENDPOINTS:
        try:
            dev.read(ep, probe, timeout=0)
            has_id = (probe[0] in range(1, 10)) and (probe[2] == 0x00)
            print("Endpoint:", hex(ep), "| report ID:", has_id)
            return ep, has_id
        except usb.core.USBTimeoutError:
            pass
        except Exception as e:
            print("Erreur sonde", hex(ep), ":", e)
    return 0x81, False

def connect_keyboard():
    dev = find_keyboard()
    if dev is None:
        return None, None, False
    try:
        dev.set_configuration()
        print("Clavier connecté :", dev.manufacturer, dev.product)
    except Exception as e:
        print("Erreur connexion :", e)
        return None, None, False
    ep, has_id = detect_endpoint(dev)
    return dev, ep, has_id

def parse_report(buf, has_id):
    if has_id:
        return buf[1], [k for k in buf[3:8] if k]
    return buf[0], [k for k in buf[2:8] if k]

# ─── Moteur de traduction ────────────────────────────────────────────
# active : touche bépo maintenue -> (mods_azerty, usage_azerty, a_consommé_altgr)
active = {}
ralt_consumed = False   # AltGr bépo absorbé par la sélection de niveau

def layer_for(modifier):
    if modifier & MOD_RALT:
        return 2
    if modifier & (MOD_LSHIFT | MOD_RSHIFT):
        return 1
    return 0

def translate(kc, modifier):
    """Retourne la liste de frappes AZERTY pour une touche bépo, ou None
    si la touche doit être transmise telle quelle."""
    entry = T.get(kc)
    if entry is None:
        return None
    shortcut = modifier & (MOD_LCTRL | MOD_RCTRL | MOD_LALT | MOD_LGUI | MOD_RGUI)
    layer = 0 if shortcut else layer_for(modifier)
    if layer not in entry:
        return None
    return entry[layer]   # () = consommée (rien)

def send_state(held_modifier):
    """Envoie l'état complet (modificateurs + touches actives) au PC."""
    out_mod = held_modifier & (MOD_LCTRL | MOD_RCTRL | MOD_LALT
                              | MOD_LGUI | MOD_RGUI)
    if held_modifier & (MOD_LSHIFT | MOD_RSHIFT):
        out_mod |= held_modifier & (MOD_LSHIFT | MOD_RSHIFT)
    if (held_modifier & MOD_RALT) and not ralt_consumed:
        out_mod |= MOD_RALT
    keys = []
    for _kc, (mods, usage, _c) in active.items():
        for ch in mods:
            out_mod |= STROKE_MODS[ch]
        keys.append(usage)
    kbd_out.release_all()
    if out_mod or keys:
        args = [MODIFIER_MAP[b] for b in MODIFIER_MAP if out_mod & b]
        args += keys
        try:
            kbd_out.press(*args)
        except Exception as e:
            print("Erreur HID :", e)

def play_sequence(strokes, held_modifier):
    """Frappes multiples (ex. « oe », accents composés) jouées à la volée."""
    for mods, usage in strokes:
        m = held_modifier & (MOD_LCTRL | MOD_RCTRL | MOD_LALT
                             | MOD_LGUI | MOD_RGUI)
        for ch in mods:
            m |= STROKE_MODS[ch]
        args = [MODIFIER_MAP[b] for b in MODIFIER_MAP if m & b]
        args.append(usage)
        try:
            kbd_out.release_all()
            kbd_out.press(*args)
            time.sleep(0.01)
            kbd_out.release(*args)
        except Exception as e:
            print("Erreur séquence :", e)

# ─── Boucle principale ───────────────────────────────────────────────
print("Adaptateur bépo → AZERTY démarré. En attente du clavier...")
kbd_dev, hid_endpoint, report_has_id = None, None, False
buf, prev_buf = bytearray(8), bytearray(8)
prev_modifier, prev_keycodes = 0, []
first = True

while True:
    if kbd_dev is None:
        kbd_dev, hid_endpoint, report_has_id = connect_keyboard()
        if kbd_dev is None:
            time.sleep(0.5)
            continue
        prev_buf[:] = bytearray(8)
        prev_modifier, prev_keycodes = 0, []

    try:
        kbd_dev.read(hid_endpoint, buf, timeout=10)
    except usb.core.USBTimeoutError:
        continue
    except Exception as e:
        print("Erreur lecture :", e)
        kbd_dev = None
        kbd_out.release_all()
        continue

    modifier, keycodes = parse_report(buf, report_has_id)
    if first and keycodes == [] and modifier == 0:
        first = False
    if modifier == prev_modifier and keycodes == prev_keycodes:
        continue
    prev_modifier, prev_keycodes = modifier, list(keycodes)

    pressed = set(keycodes)
    held = set(k for k in active)

    # — Nouvelles touches pressées —
    for kc in pressed - held:
        if 0xE0 <= kc <= 0xE7:
            continue
        strokes = translate(kc, modifier)
        if strokes is None:                       # transmission directe
            active[kc] = ("", kc, False)
        elif len(strokes) == 0:                    # consommée
            active[kc] = None
        elif len(strokes) == 1:
            mods, usage = strokes[0]
            consumed = (kc in T) and (2 in T[kc]) and \
                       (strokes is T[kc][2])
            active[kc] = (mods, usage, consumed)
        else:
            play_sequence(strokes, modifier)
            active[kc] = None

    # — Touches relâchées —
    for kc in held - pressed:
        active.pop(kc, None)

    # — AltGr consommé ? (sélecteur de niveau bépo absorbé) —
    ralt_consumed = any(
        c for (_m, _u, c) in active.values() if c is not None
    )

    # — Envoi de l'état —
    send_state(modifier)