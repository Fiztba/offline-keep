"""Derived world-state flags and consistency warnings.

The game stores many decisions twice: once as a multi-value "state" variable and again as
yes/no flags (e.g. dao_warden_background plus dao_warden_background_city_elf). The user only
answers the primary questions; derive() fills in everything that follows from them.
Value meanings come from the game's own VaultGroupUIDescription text unless noted.
"""

DAO_BACKGROUNDS = ["human_noble", "human_mage", "dalish_elf", "city_elf", "elven_mage", "dwarf_noble",
                   "dwarf_commoner"]
BACKGROUND_RACE = [0, 0, 1, 1, 1, 2, 2]  # human, elf, dwarf
MAGE_BACKGROUNDS = {1, 4}
DAO_ROMANCES = [None, "alistair", "morrigan", "leliana", "zevran"]
DA2_ROMANCES = ["none", "anders", "fenris", "isabela", "merrill", "sebastian"]
CLASSES = ["warrior", "rogue", "mage"]


def _b(cond):
    return 1 if cond else 0


def derive(v):
    """Fill in every dependent variable of `v` (a name -> int dict) in place and return it."""
    # --- Origins: the Warden
    bg = v["dao_warden_background"]
    if bg in MAGE_BACKGROUNDS:
        v["dao_warden_class"] = 2
    elif v["dao_warden_class"] == 2:
        v["dao_warden_class"] = 0
    v["dao_warden_race"] = BACKGROUND_RACE[bg]
    for i, name in enumerate(DAO_BACKGROUNDS):
        v[f"dao_warden_background_{name}"] = _b(bg == i)
    for i, race in enumerate(["human", "elf", "dwarf"]):
        v[f"dao_warden_race_{race}"] = _b(v["dao_warden_race"] == i)
    for i, cls in enumerate(CLASSES):
        v[f"dao_warden_class_{cls}"] = _b(v["dao_warden_class"] == i)
    v["dao_warden_is_male"] = _b(v["dao_warden_mf"] == 0)
    v["dao_warden_is_female"] = _b(v["dao_warden_mf"] == 1)
    for i, who in enumerate(DAO_ROMANCES):
        if who:
            v[f"dao_warden_romance_{who}"] = _b(v["dao_warden_romance"] == i)
    v["dao_warden_alive"] = _b(v["dao_warden_state"] != 0)

    # --- Origins: the end of the Blight
    killer = v["dao_archdemon_killer"]  # 0 Warden, 1 Alistair, 2 Loghain
    if v["dao_warden_state"] == 0:
        killer = v["dao_archdemon_killer"] = 0
    if v["dao_alistair_state"] == 0:
        killer = v["dao_archdemon_killer"] = 1
    if v["dao_loghain_fate"] == 2:
        killer = v["dao_archdemon_killer"] = 2

    a = v["dao_alistair_state"]  # 0 died vs Archdemon, 1 executed, 2 king, 3 Warden, 4 drunk
    v["dao_alistair_alive"] = _b(a not in (0, 1))
    v["dao_alistair_executed"] = _b(a == 1)
    v["dao_alistair_killed_archdemon"] = _b(killer == 1)
    v["dao_alistair_royal_status"] = _b(a == 2)
    v["dao_alistair_drunk"] = _b(a == 4)

    r = v["dao_ruler_state"]  # 0 Alistair, 1 Alistair+Anora, 2 Alistair+Warden, 3 Anora, 4 Anora+Warden
    v["dao_alistair_king_alone"] = _b(r == 0)
    v["dao_alistair_king_with_anora"] = _b(r == 1)
    v["dao_alistair_king_with_warden"] = _b(r == 2)
    v["dao_anora_queen_alone"] = _b(r == 3)
    v["dao_anora_queen_with_warden"] = _b(r == 4)
    v["dao_anora_queen_alone_or_with_warden"] = _b(r in (3, 4))
    v["dao_warden_married_alistair"] = _b(r == 2)
    v["dao_warden_married_alistair_anora"] = _b(r == 4)  # per Custom World States notes: married Anora

    lf = v["dao_loghain_fate"]  # 0 executed by Warden, 1 executed by Alistair, 2 died vs Archdemon, 3 alive
    v["dao_loghain_executed"] = {0: 1, 1: 2}.get(lf, 0)
    v["dao_loghain_killed_archdemon"] = _b(killer == 2)
    v["dao_loghain_alive"] = _b(lf == 3)
    v["dao_loghain_recruited"] = _b(lf in (2, 3))

    mb = v["dao_morrigan_baby"]  # 0 none, 1 Warden, 2 Alistair, 3 Loghain (4 = human child, experimental)
    v["dao_morrigan_baby_warden"] = _b(mb in (1, 4))
    v["dao_morrigan_baby_alistair"] = _b(mb == 2)
    v["dao_morrigan_baby_loghain"] = _b(mb == 3)
    v["dao_morrigan_has_child"] = _b(mb > 0)
    v["dao_morrigan_dark_ritual"] = _b(mb in (1, 2, 3))
    v["dao_morrigan_dark_ritual_warden"] = _b(mb == 1)

    # --- Origins: quests and companions
    lel = v["dao_leliana_fate"]  # 0 not recruited, 1 alive, 2 killed after poisoning Urn, 3 killed otherwise
    v["dao_leliana_recruited"] = _b(lel != 0)
    v["dao_leliana_alive"] = _b(lel == 1)
    v["dao_leliana_killed_sacred_ashes"] = _b(lel == 2)
    v["dao_leliana_killed"] = _b(lel == 3)
    v["dao_leliana_crisis"] = _b(lel == 3)
    if lel == 2:
        v["dao_urn_of_sacred_ashes_destroyed"] = 1

    c = v["dao_connor_state"]  # 0 dead, 1 alive, 2 alive and possessed
    v["dao_connor_dead"] = _b(c == 0)
    v["dao_connor_alive_and_not_possessed"] = _b(c == 1)
    v["dao_connor_alive_and_possessed"] = _b(c == 2)

    v["dao_broken_circle_mages"] = _b(v["dao_broken_circle_choice"] == 0)
    v["dao_broken_circle_templars"] = _b(v["dao_broken_circle_choice"] == 1)

    n = v["dao_nb_werewolf_elf_choice"]  # 0 peace, 1 werewolves, 2 elves
    v["dao_ntb_brokered_peace"] = _b(n == 0)
    v["dao_ntb_side_werewolves"] = _b(n == 1)
    v["dao_ntb_side_elves"] = _b(n == 2)

    v["dao_harrowmont_is_king"] = _b(v["dao_orzammar_ruler"] == 0)
    v["dao_bhelen_is_king"] = _b(v["dao_orzammar_ruler"] == 1)
    branka = v["dao_paragon_chosen"] == 1
    v["dao_par_chose_caridin"] = _b(not branka)
    v["dao_par_chose_branka"] = _b(branka)
    if not branka:
        v["dao_paragon_anvil_fate"] = 0
    elif v["dao_paragon_anvil_fate"] == 0:
        v["dao_paragon_anvil_fate"] = 2
    anvil = v["dao_paragon_anvil_fate"]  # 0 destroyed for Caridin, 1 Branka destroyed it, 2 Branka kept it
    v["dao_par_caridin_destroyed_anvil"] = _b(anvil == 0)
    v["dao_par_branka_destroyed_anvil"] = _b(anvil == 1)
    v["dao_par_branka_kept_anvil"] = _b(anvil == 2)
    v["dao_par_dagna_circle"] = _b(v["dao_par_unlikely_scholar"] == 3)

    v["dao_wynne_recruited"] = _b(v["dao_wynne_fate"] != 0)
    if not v["dao_shale_recruited"]:
        v["dao_shale_fate"] = 0

    # --- Dragon Age II: Hawke
    v["da2_hawke_is_male"] = _b(v["da2_hawke_mf"] == 0)
    v["da2_hawke_is_female"] = _b(v["da2_hawke_mf"] == 1)
    v["da2_hawke_appearance"] = v["da2_hawke_mf"]
    for i, cls in enumerate(CLASSES):
        v[f"da2_hawke_class_{cls}"] = _b(v["da2_hawke_class"] == i)
    for i, p in enumerate(["diplomatic", "humourous", "aggressive"]):
        v[f"da2_hawke_personality_{p}"] = _b(v["da2_hawke_personality_type"] == i)
    for i, who in enumerate(DA2_ROMANCES):
        v[f"da2_hawke_romance_{who}"] = _b(v["da2_hawke_romance"] == i)
    v["da2_sided_with_mages"] = _b(v["da2_hawke_chosen_side"] == 0)
    v["da2_sided_with_templars"] = _b(v["da2_hawke_chosen_side"] == 1)
    v["da2_varric_friendship"] = _b(v["da2_hawke_varric_relationship"] == 0)

    # --- Dragon Age II: siblings (career: 0 died leaving Lothering, 1 Circle/templar, 2 Warden, 3 died in Deep Roads)
    beth, carv = v["da2_bethany_career"], v["da2_carver_career"]
    if beth in (0, 3):
        v["da2_bethany_final_battle_death"] = 0
    elif v["da2_bethany_final_battle_death"] == 0:
        v["da2_bethany_final_battle_death"] = 1
    v["da2_bethany_alive"] = _b(beth in (1, 2) and v["da2_bethany_final_battle_death"] != 2)
    v["da2_bethany_is_warden"] = _b(beth == 2)
    v["da2_bethany_died_deep_roads"] = _b(beth == 3)
    v["da2_carver_alive"] = _b(carv in (1, 2))
    v["da2_carver_is_warden"] = _b(carv == 2)
    v["da2_carver_died_deep_roads"] = _b(carv == 3)

    # --- Dragon Age II: companions
    anders = v["da2_anders_fate"]  # 0 alive, 1 executed (game text has these reversed; defaults confirm)
    v["da2_anders_alive"] = _b(anders == 0)
    v["da2_anders_executed"] = _b(anders == 1)
    fen = v["da2_fenris_alive"]  # 0 not recruited, 1 died, 2 alive, 3 returned to master (4 = pursued, experimental)
    v["da2_fenris_joined"] = _b(fen != 0)
    v["da2_fenris_enslaved"] = 0 if fen == 0 else (2 if fen == 3 else 1)
    v["da2_fenris_returned_to_master"] = _b(fen == 3)
    v["da2_fenris_still_alive"] = _b(fen in (2, 3, 4))
    # Isabela: returned_with_book 0 not recruited, 1 no, 2 yes; turned_over 0 not there, 1 no, 2 yes.
    # The game's own default world state recruits her but leaves both at 0, so fill in consistent answers.
    if v["da2_hawke_romance"] == 3:
        v["da2_isabela_joined"] = 1
    if not v["da2_isabela_joined"]:
        v["da2_isabela_returned_with_book"] = 0
    elif v["da2_isabela_returned_with_book"] == 0:
        v["da2_isabela_returned_with_book"] = 2
    if v["da2_isabela_returned_with_book"] != 2:
        v["da2_isabela_turned_over"] = 0  # she wasn't there to be turned over
    elif v["da2_isabela_turned_over"] == 0:
        v["da2_isabela_turned_over"] = 1
    v["da2_bartrand_alive"] = _b(v["da2_varric_bartrand_killed"] == 0)
    v["da2_legacy_hawke_sided_with_larius"] = _b(v["da2_dlc_legacy_played"] and v["da2_legacy_side_chosen"] == 0)
    v["da2_legacy_hawke_sided_with_janeka"] = _b(v["da2_dlc_legacy_played"] and v["da2_legacy_side_chosen"] == 1)

    v["dao_or_da2_played"] = _b(v["dao_played"] or v["da2_played"])
    return v


class _Recorder(dict):
    def __setitem__(self, key, value):
        self.written.add(key)
        super().__setitem__(key, value)


def derived_names(values):
    """Names of the variables derive() sets (computed rather than asked)."""
    rec = _Recorder(values)
    rec.written = set()
    derive(rec)
    return rec.written


def warnings(v):
    """Combinations the original games could not produce (allowed, but worth pointing out)."""
    w = []
    r, a = v["dao_ruler_state"], v["dao_alistair_state"]
    if r in (0, 1, 2) and a != 2:
        w.append("Alistair rules Ferelden, but his fate isn't \"He becomes King\".")
    if r in (3, 4) and a == 2:
        w.append("Alistair is King, but Anora is chosen as ruler without him.")
    if r in (2, 4) and v["dao_warden_state"] == 0:
        w.append("The Warden rules Ferelden but died killing the Archdemon.")
    if r == 2 and v["dao_warden_mf"] == 0:
        w.append("A male Warden can't marry King Alistair in Origins.")
    if r == 4 and v["dao_warden_mf"] == 1:
        w.append("A female Warden can't marry Queen Anora in Origins.")
    if v["dao_loghain_fate"] in (2, 3) and a == 2:
        w.append("Loghain was spared to join the Wardens, which normally means Alistair doesn't become King.")
    if v["dao_morrigan_baby"] == 2 and a in (0, 1):
        w.append("Morrigan had Alistair's child, but Alistair didn't survive the Landsmeet.")
    if v["dao_morrigan_baby"] == 3 and v["dao_loghain_fate"] in (0, 1):
        w.append("Morrigan had Loghain's child, but Loghain was executed.")
    if v["dao_morrigan_baby"] in (1, 4) and v["dao_warden_mf"] == 1:
        w.append("Morrigan had the Warden's child, which requires a male Warden.")
    if v["dao_morrigan_baby"] == 4 and v["dao_warden_romance"] != 2:
        w.append("Morrigan had the Warden's child without the Dark Ritual, but the Warden didn't romance her.")
    if v["dao_morrigan_baby"] in (1, 2, 3) and v["dao_warden_state"] == 0:
        w.append("The Dark Ritual was performed, yet the Warden died killing the Archdemon.")
    if v["dao_warden_romance"] == 1 and v["dao_warden_mf"] == 0:
        w.append("Alistair only romances a female Warden.")
    if v["dao_warden_romance"] == 2 and v["dao_warden_mf"] == 1:
        w.append("Morrigan only romances a male Warden.")
    if v["dao_warden_romance"] == 3 and v["dao_leliana_fate"] in (0, 2, 3):
        w.append("The Warden romanced Leliana, but she wasn't recruited or was killed.")
    if v["dao_warden_romance"] == 4 and not v["dao_zevran_recruited"]:
        w.append("The Warden romanced Zevran, but he wasn't recruited.")
    if v["dao_warden_king_mistress"] and v["dao_warden_romance"] != 1:
        w.append("The Alistair relationship answer is set, but the Warden didn't romance Alistair.")

    beth, carv = v["da2_bethany_career"], v["da2_carver_career"]
    if beth in (0, 3) and carv in (0, 3):
        w.append("Both Hawke siblings died; in Dragon Age II one always survives Lothering.")
    if beth != 0 and carv != 0:
        w.append("Both Hawke siblings survived Lothering; in Dragon Age II one always dies there.")
    # The sibling who shares Hawke's role dies: mage Hawke loses Bethany, warrior Hawke loses Carver.
    if v["da2_hawke_class"] == 0 and beth == 0:
        w.append("Bethany died leaving Lothering, which can't happen when Hawke is a warrior.")
    if v["da2_hawke_class"] == 2 and carv == 0:
        w.append("Carver died leaving Lothering, which can't happen when Hawke is a mage.")
    rom = v["da2_hawke_romance"]
    if rom == 1 and v["da2_anders_fate"] == 1:
        w.append("Hawke romanced Anders, who was then executed (possible, but intentional?).")
    if rom == 2 and v["da2_fenris_alive"] in (0, 1):
        w.append("Hawke romanced Fenris, but he wasn't recruited or died.")
    if rom == 3 and v["da2_isabela_turned_over"] == 2:
        w.append("Hawke romanced Isabela, then handed her over to the Arishok.")
    if rom == 5 and not v["da2_sebastian_joined"]:
        w.append("Hawke romanced Sebastian, but he wasn't recruited.")
    if not v["dao_played"] and not v["da2_played"]:
        w.append("Neither Origins nor Dragon Age II is marked as played; the game may ignore these choices.")
    return w
