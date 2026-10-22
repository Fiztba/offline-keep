"""The questions the app asks, built from the game's own Keep text (VaultGroupUIDescription)."""
from dataclasses import dataclass, field

# Choices the game has no description text for, or whose text is wrong. Labels for these come
# from community documentation (Custom World States reference by anshela).
CUSTOM = {
    "dao_wynne_fate": ("What happened to Wynne?",
                       {0: "The Warden did not recruit Wynne", 1: "Wynne is alive and well",
                        2: "Wynne died at the Broken Circle", 3: "Wynne was killed after the Urn was poisoned"}),
    "dao_isolde_state": ("Did Isolde sacrifice herself to save Connor?", {0: "No", 1: "Yes"}),
    "dao_paragon_anvil_fate": ("What happened to the Anvil of the Void?",
                               {0: "Destroyed at Caridin's request", 1: "Branka destroyed it",
                                2: "Branka kept it"}),
    "dao_shale_recruited": ("Did the Warden recruit Shale?", {0: "No", 1: "Yes"}),
    "da2_dlc_legacy_played": ("Was the Legacy DLC played?", {0: "No", 1: "Yes"}),
    "da2_act3_samson_reinstated": ("What happened to Samson?",
                                   {0: "Samson was killed", 1: "Samson was reinstated into the templars"}),
    "da2_merrill_alive": ("What happened to Merrill?", {0: "Merrill died", 1: "Merrill is alive and well"}),
    "da2_merrils_clan": ("Was Merrill's clan destroyed?", {0: "No", 1: "Yes"}),
    "da2_anders_fate": ("What happened to Anders?", {0: "He is alive and well", 1: "He was executed by Hawke"}),
}

SECTIONS = [
    ("Dragon Age: Origins", [
        ("The Warden", ["dao_played", "dao_warden_background", "dao_warden_mf", "dao_warden_class",
                        "dao_warden_romance", "dao_warden_state", "dao_warden_eluvian"]),
        ("Ostagar & Lothering", ["dao_pre_hungry_deserter", "dao_pre_mabari_hound", "dao_dog_recruited",
                                 "dao_lot_qunari_prisoner", "dao_sten_recruited", "dao_sten_sword"]),
        ("Circle Tower", ["dao_broken_circle_choice", "dao_bc_irving_survive", "dao_wynne_fate"]),
        ("Redcliffe", ["dao_red_village_siege", "dao_red_attack_nightfall", "dao_connor_state", "dao_isolde_state",
                       "dao_red_missing_child", "dao_red_lost_castle"]),
        ("Brecilian Forest", ["dao_nb_werewolf_elf_choice", "dao_ntb_*"]),
        ("Orzammar", ["dao_orzammar_ruler", "dao_paragon_chosen", "dao_paragon_anvil_fate", "dao_oghren_recruited",
                      "dao_par_*", "dao_dno_mardy_son"]),
        ("Urn of Sacred Ashes", ["dao_urn_of_sacred_ashes_destroyed", "dao_leliana_fate"]),
        ("Denerim", ["dao_den_*"]),
        ("Companions", ["dao_zevran_recruited", "dao_zevran_alive", "dao_shale_recruited", "dao_morrigan_baby"]),
        ("Landsmeet & Archdemon", ["dao_loghain_fate", "dao_alistair_state", "dao_ruler_state",
                                   "dao_warden_king_mistress", "dao_archdemon_killer"]),
        ("Awakening", ["dao_awakenings_played", "dao_awakenings_nathaniel_live"]),
    ]),
    ("Dragon Age II", [
        ("Hawke", ["da2_played", "da2_hawke_mf", "da2_hawke_class", "da2_hawke_personality_type",
                   "da2_hawke_romance", "da2_hawke_varric_relationship", "da2_hawke_chosen_side",
                   "da2_hawke_approves_of_anders_action"]),
        ("Family", ["da2_bethany_career", "da2_bethany_final_battle_death", "da2_carver_career"]),
        ("Act 1", ["da2_pro_choice", "da2_act1_*"]),
        ("Act 2", ["da2_act2_*", "da2_arishok_killed"]),
        ("Act 3", ["da2_act3_*"]),
        ("Companions", ["da2_anders_fate", "da2_aveline_married", "da2_aveline_remained", "da2_fenris_alive",
                        "da2_isabela_joined", "da2_isabela_returned_with_book", "da2_isabela_turned_over",
                        "da2_merrill_alive", "da2_merrill_remained", "da2_merrill_eluvian_destroy",
                        "da2_merrils_clan", "da2_sebastian_joined", "da2_varric_bartrand_killed",
                        "da2_varric_has_idol_piece", "da2_varric_plot_complete"]),
        ("Legacy", ["da2_dlc_legacy_played", "da2_legacy_side_chosen", "da2_legacy_malcolm_will"]),
        ("Mark of the Assassin", ["da2_mark_tallis_angry", "da2_mark_tallis_kiss"]),
    ]),
]


@dataclass
class Question:
    var: str
    text: str
    options: dict  # value -> label, one entry per distinct answer (offered in the dropdown)
    game_default: int
    labels: dict = field(default_factory=dict)  # every value the game describes, duplicates included

    def label_for(self, value):
        """Display text for a value, marking hidden duplicate values so they stay distinguishable."""
        if value in self.options:
            return self.options[value]
        if value in self.labels:
            return f"{self.labels[value]} (value {value})"
        return None


# Typos in the game's own Keep text, corrected for display only.
TEXT_FIXES = {"Cured it with the wilds flower.": "Cured it with the wild flowers."}


def _distinct(options):
    """Keep the lowest value for each answer text (the game lists some answers under several values)."""
    out, seen = {}, set()
    for value, label in sorted(options.items()):
        if label not in seen:
            seen.add(label)
            out[value] = label
    return out


@dataclass
class Section:
    game: str
    title: str
    questions: list = field(default_factory=list)


def _game_text(ws):
    """var name -> (question, {value: answer}) from the game's description objects."""
    by_flag = {}
    for o in ws.objects:
        if o["$type"] == "VaultGroupUIDescription":
            by_flag.setdefault(o["PlotFlag"]["PlotFlagId"]["Guid"], []).append(o)
    out = {}
    for name, var in ws.vars.items():
        descs = by_flag.get(var["PlotFlag"]["PlotFlagId"]["Guid"])
        if not descs:
            continue
        question, options = None, {}
        for d in descs:
            q, _, answer = d["DisplayString"].lstrip("$").partition("  ")
            question = question or q.strip()
            answer = TEXT_FIXES.get(answer.strip(), answer.strip())
            for value in d["TriggerValues"]:
                options[value] = answer
        out[name] = (question, dict(sorted(options.items())))
    return out


def build_sections(ws):
    text = _game_text(ws)
    text.update(CUSTOM)
    sections = []
    for game, groups in SECTIONS:
        for title, patterns in groups:
            sec = Section(game, title)
            seen = set()
            for pat in patterns:
                names = ([n for n in ws.vars if n.startswith(pat[:-1])] if pat.endswith("*") else [pat])
                for n in names:
                    if n in seen or n not in text or n in DERIVED:
                        continue
                    seen.add(n)
                    q, opts = text[n]
                    sec.questions.append(Question(n, q, _distinct(opts), ws.vars[n]["DefaultValue"], opts))
            sections.append(sec)
    return sections


# Variables computed by rules.derive() and therefore never asked directly.
DERIVED = {
    "dao_warden_race", "dao_warden_alive", "dao_alistair_alive", "dao_alistair_executed",
    "dao_alistair_killed_archdemon", "dao_alistair_royal_status", "dao_loghain_executed",
    "dao_loghain_killed_archdemon", "dao_loghain_alive", "dao_loghain_recruited", "dao_morrigan_baby_warden",
    "dao_morrigan_baby_alistair", "dao_morrigan_baby_loghain", "dao_leliana_recruited", "dao_leliana_alive",
    "dao_leliana_killed", "dao_leliana_killed_sacred_ashes", "dao_wynne_recruited", "dao_par_dagna_circle",
    "da2_anders_alive", "da2_anders_executed", "da2_bethany_alive", "da2_carver_alive", "da2_fenris_joined",
    "da2_fenris_enslaved",
}


def primary_vars(sections):
    return {q.var for s in sections for q in s.questions}
