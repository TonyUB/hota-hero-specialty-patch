# AGENTS.md — HotA 1.8.0 Binary Patch Project

## Trusted baseline

- The only trusted modified baseline is `Patch_v1.8.zip`.
- Never build on Patch_v1.9, v2.0, v2.1, v2.2, or v2.3.
- Historical test packages and failed binaries are no longer retained in the
  repository. Their conclusions are preserved under `CHANGELOG/` and `analysis/`.
- `Download/HOTA_NEW_HERO_V1.2.zip` is the current formal release.

## Current milestone

V1.2 is the current formal specialty release. It uses V1.14 as its sole
source and replaces Coronius's native Slayer specialty with the accepted
Scholar specialty. Coronius's Scholar contribution functions one level higher;
when he participates in a hero meeting, both heroes' Wisdom receive caps also
increase by one, with the native level-5 ceiling retained. Four local wrappers
inside the previously empty `.luck3` tail implement the calculations without
temporarily changing hero fields. Coronius keeps Basic Wisdom + Basic Scholar,
his spell book, and starting Slayer. His native specialty-table type changes
from spell specialty `3` to the game's existing disabled value `-1`, so the old
Slayer bonus panel and runtime amplification are unreachable. The correct
native Expert Scholar frame is `59` (`skill19c` / `skl3219c`). Formal V1.2
removes the diagnostic entry hook, log strings, and writer used by tests. Full
rollback, independent verification, deterministic builds, and standard startup
to the main menu pass; the user accepted all TEST04 gameplay and presentation
items before formalization.

V1.14 is the inherited formal balance release. It inherits every V1.13 gameplay
mechanic and changes only two default-hero fields in both executables: Melodia's
second secondary skill changes from Basic Mysticism (ID 8) to Basic Leadership
(ID 6), while Daremyth's starting spell changes from Magic Arrow (ID 15) to
View Air (ID 5). Melodia keeps Basic Wisdom, her spellbook, and Mirth;
Daremyth keeps Basic Wisdom + Basic Intelligence and her spellbook. Full-record
checks, allowed-byte checks, PE checksums, deterministic builds, independent
verification, rollback, and standard/HD startup gates pass.

V1.13 is the inherited formal data release. It inherits V1.12 byte-for-byte
except for Daremyth's starting-spell field in the standard and HD executables
and the root installation text. Daremyth keeps Basic Wisdom + Basic
Intelligence and her spellbook, but starts with Magic Arrow (ID 15) instead of
Mirth (ID 49). Melodia continues to start with Mirth; Uland and Astra continue
to start with Cure. The fixed Luck `+3`, per-stack first-active-attack
guarantee, native hard-disable boundary, Cure system, and every other gameplay
path remain unchanged. Full-record checks, PE checksums, deterministic builds,
independent verification, rollback, and standard/HD startup gates pass.

V1.12 is the inherited formal specialty release. It preserves V1.11's accepted
fixed Luck `+3` for Melodia and Daremyth and adds a per-stack, per-battle first
active attack guarantee. Only active melee/ranged commands consume eligibility;
retaliation, wait, defend, and spellcasting do not. Repeated hits within the
same command share the guarantee, and subsequent commands use native `+3` Luck.
The native Hourglass/Cursed Ground hard-disable boundary still takes priority.
The formal payload removes TEST2's diagnostic writer and passed reproducible
builds, independent verification, runtime hook inspection, and standard/HD
startup gates. Chinese and English landing-page descriptions match.

V1.1 is the inherited formal specialty release. It inherits the complete V1.06
gameplay payload and adds fixed-Luck specialties for Melodia (hero ID 29) and
Daremyth (hero ID 43). After the native Cursed Ground / Hourglass hard-disable
gate passes, both heroes return final Luck `+3`, bypassing ordinary positive
and negative numeric modifiers. The native hard-disable return remains before
the new hook and therefore still prevents lucky strikes. Melodia starts with
Basic Wisdom + Basic Mysticism; Daremyth keeps Basic Wisdom + Basic
Intelligence; both spell books start with Mirth. The standard and HD
executables, two HotA LOD copies, and the loose Chinese HeroSpec override match
the user-accepted `HOTA_NEW_HERO_V1.1_LUCK_TEST1` byte-for-byte.

V1.06 is the inherited formal numerical release. It inherits the complete V1.05
gameplay payload and adds Cure UI synchronization for Uland and Astra. The
spell book displays the current tier-1 through tier-7 F7 range, and hovering a
living friendly stack displays that stack's exact F7 total. Corpse-hover text
intentionally remains native Cure text. The user accepted all UI_TEST2 runtime
items; the formal package is byte-identical to that accepted `HotA.dll` and has
passed static, rollback, ZIP CRC, reproducible-build, and standard-executable
startup gates:

- Preserve all accepted Stage 2 behavior for living stacks.
- Uland and Astra may target a fully dead friendly stack with single-target Cure
  only when native Resurrection target lookup accepts that corpse.
- A fully dead stack receives the complete Cure amount through native permanent
  resurrection; never call the living-only Cure core on a corpse.
- Expert Water Magic mass Cure resolves living stacks first, then scans fully
  dead friendly stacks and applies the same native Resurrection restrictions.
- Reuse native corpse lookup, placement, occupancy, animation, eligibility, and
  `ResurrectTarget(..., temporary=0)`.
- The real single-target cast path performs an additional Cure effect/resistance
  check at `0x005A05FA`. For a fully dead specialist target, bypass it only after
  `GetResurrectionTarget(..., context=0)` returns that exact stack again.
- `Download/HOTA_NEW_HERO_V1.04.zip` historically inherited the runtime-accepted V1 Cure,
  presentation, log-order, and Elf implementation. It corrects V1.03's
  zero-based creature-tier conversion, adds per-stack localized treatment
  lines, and synchronizes the HotA description/detail panel with F6.
- Astra starts with Basic Wisdom + Basic Water Magic. The release performs this
  as a direct `HotA.dat` patch to `Heroes\hero170.str`: second-skill type `9`
  (Luck) becomes `16` (Water Magic), while its Basic level, spellbook, and
  starting Cure spell remain unchanged.
- V1.05 and V1.06 Cure use F7 NativePower:
  `H = floor(((11L + 29) * (clamp(n,1,7) + 11)) / 12) + 5 * (P - 1) + 10 * max(0, clamp(w,0,3) - 1)`.
  Here `L>=1`, effective `P>=0`, `n=1..7`, and `w=0/1/2/3` means
  none/basic/advanced/expert Water Magic. Every extra point of Power adds 5;
  Advanced/Expert Water add 10/20 over None/Basic after the integer division.
  The standard and HD executables use the same payload, and the specialty
  detail panel uses the same total. Native single-target versus mass-target
  rules remain unchanged.
- V1.03 and V1.04 historically used F6 Direct:
  `H = floor((11L + 10P + 19) * (clamp(n,1,7) + 11) / 12) + 10 * max(0, clamp(w,0,3) - 1)`.
  Here `w=0/1/2/3` means none/basic/advanced/expert Water Magic. The Water
  bonus is therefore `0/0/10/20` and is added after integer division. Native
  single-target versus mass-target rules remain unchanged. Both living and
  fully dead specialist targets finish at the same custom total;
  non-specialists tail-call the original bonus function.
- Runtime testing of `HOTA_NEW_HERO_V1.04_LOG_TEST1` exposed a V1.03
  implementation error that the earlier static sample matrix could not catch:
  `H3CombatCreature +0x74` is its copied `H3CreatureInformation`, so `+0x78`
  is the zero-based creature level `0..6`. V1.03 incorrectly evaluated
  `7 - [stack+0x78]`, making a level-1 creature use tier 7. Formal V1.04 uses
  `clamp([stack+0x78] + 1, 1, 7)`.
- `HOTA_NEW_HERO_V1.04_LOG_TEST1` is withdrawn. Its single-target treatment
  line passed, but its mass treatment records were absent because it cleared
  living records at the later corpse-scan initializer and did not hook the
  direct mass-corpse calculator call at `0x00639C98`.
- `HOTA_NEW_HERO_V1.04_LOG_TEST2` passed battle-runtime acceptance for single
  and mass Cure, living and fully-dead stacks, per-stack treatment totals, F6
  values, and the final order “native Cure line -> all treatment totals ->
  native resurrection lines”. It was not promoted because its terse
  `creature: +H` wording still needed localization and the specialty detail
  panel continued to use HotA.dat/HotA.dll's native `8-n` text and values.
- `HOTA_NEW_HERO_V1.04_UI_TEST3` is the accepted release candidate. It keeps all TEST2
  settlement behavior, uses the localized `creature obtains H healing` line,
  updates `Heroes\hero170.str` inside HotA.dat, and redirects only Uland/Astra
  Cure specialty-panel calculations to the same F6 total. Its effect column is
  `H`; its integer bonus column is `floor((H-(5P+30))*100/(5P+30))`. Static,
  reproducible-build, rollback, and standard/HD 12-second startup gates pass.
  User testing confirmed the new wording, both detail panels, and all gameplay
  paths; its runtime payload was promoted to formal V1.04.
- The Chinese HD pack's loose
  `_HD3_Data\Packs\H3中文-基础资源\HeroSpec.txt` overrides both HotA LOD copies.
  Any Cure-description release must patch and verify this loose file as well as
  the two LOD entries.
- V1.01 was withdrawn and its package removed: it incorrectly treated the
  requested formula as the expert-Water result and preserved native -20/-10
  mastery differences. Its SHA-256 and lesson remain in `CHANGELOG/`.

Stage 4 development history:

- `TEST/Patch_v2.6_VISUAL_TEST1.zip` proved that skipping the whole native
  visual block preserves resurrection state, but mass Cure left revived stacks
  displayed as corpses until a mouse-over forced a redraw.
- `TEST/Patch_v2.6_VISUAL_TEST2.zip` is withdrawn after a runtime crash at
  `HotA.dll+0x64AFF`. Supplying effect id `-1` cleared the native effect object,
  but HotA's extra battle renderer dereferenced that pointer without a null check.
- `TEST/Patch_v2.6_VISUAL_TEST3.zip` passed startup, crash prevention, Cure
  presentation/sound, circle suppression, Resurrection-sound suppression, and
  single/mass resurrection. It stopped revived creatures on death-animation
  frame zero (visually the hit pose) because it ran exactly `N` reverse frames.
- `TEST/Patch_v2.6_VISUAL_TEST4.zip` passed all runtime gates: startup,
  single/mass resurrection, quantities, permanence, undead exclusion,
  overlapping corpses, occupied corpses, Cure-only sound/effect isolation,
  per-stack redraw, stand-up completion, and ordinary Resurrection behavior.
  Its only remaining issue was cosmetic combat-log ordering: native revival
  lines appeared before the outer Cure cast line.
- `TEST/Patch_v2.6_VISUAL_TEST5.zip` is withdrawn. Single Cure passed, but mass
  Cure crashed at `HotA.dll+0x38060`: the mass cast-message routine received a
  null explicit target before `[battle+0x547C]` had been initialized with the
  affected stacks.
- `TEST/Patch_v2.6_VISUAL_TEST6.zip` is withdrawn. Mass Cure still crashed; the
  direct return address `0x005A1B82` is immediately after the native effect
  check. HotA requires each target's check to be followed immediately by its
  settlement, so TEST6's two-phase validation/application split was unsafe.
- `TEST/Patch_v2.6_VISUAL_TEST7.zip` is withdrawn. Its single-target path put
  the Cure line before the revival line correctly, but mass Cure crashed at
  `0x005A1B78`, inside TEST7's reassembled target-index loop and before its
  corpse helper, cast formatter, or log-rotation helper ran.
- `TEST/Patch_v2.6_VISUAL_TEST8.zip` proved that restoring TEST4's mass-Cure
  instruction addresses prevents the crash. Mass resurrection passed again,
  but the Cure cast line still appeared after revival lines, so the record hook
  at `0x005A1B30` did not produce an effective rotation start. Its compact
  helper also contained a statically detected wrapped `JECXZ` target outside
  the cave (`0x00639BB5`); the normal specialist path did not take that branch.
- `TEST/Patch_v2.6_VISUAL_TEST9.zip` restores TEST4's original instruction at
  `0x005A1B30`, moves the same-size record hook to the mandatory table-clear
  count at `0x005A1B36`, preserves all bytes from `0x005A1B3B` through
  `0x005A1BFA`, and fixes the `JECXZ` target inside the validated cave. Runtime
  testing proved single-Cure ordering and mass stability, but mass Cure still
  displayed its cast line after every revival line.
- `TEST/Patch_v2.6_VISUAL_TEST10.zip` moves the record hook to the mandatory
  stack-count read at `0x005A1B48` and the rotation hook to the post-formatter
  argument setup at `0x005A1C00`. Both same-length trampolines replay the exact
  displaced instructions. Runtime testing still showed the mass Cure line last,
  proving these independent trampolines did not enter the live display chain.
- `TEST/Patch_v2.6_VISUAL_TEST11.zip` instead wraps the observable native calls
  at `0x005A1B97` and `0x005A1BF6`. The first effective target check records the
  log boundary; the native Cure formatter itself returns through the pointer
  rotation and native refresh continuation.
- Runtime testing proved that TEST11 still left the mass Cure cast line after
  all revival lines, so HotA/HD did not use those outer call continuations for
  the live ordering path.
- `TEST/Patch_v2.6_VISUAL_TEST12.zip` hooks inside native Cure logger
  `0x005A8C60`, immediately after its real append call at `0x005A9547`.
  A mass-scoped byte counts each Cure-only resurrection entry; the post-append
  helper rotates the final Cure pointer backward by that exact count, refreshes
  the native log, and replays the displaced instructions.
- Runtime testing proved that TEST12 still displayed the mass Cure cast line
  after every revival line. Do not continue changing ordering blindly.
- `TEST/Patch_v2.6_VISUAL_LOGDIAG01.zip` keeps TEST12 behavior and writes
  `hota_cure_logdiag01.bin`. One mass Cure records wrapper/helper entry, each
  Cure-only resurrection count, and vector snapshots immediately after native
  append, after rotation, and after native refresh.
- The returned LOGDIAG01 file contains 21 records. Four Cure-only resurrection
  entries advanced the state through `0x81` to `0x84`; the Cure pointer was
  moved to the intended insertion slot and remained there after `0x00472770`.
  The screenshot nevertheless kept the Cure line last. This proves the visible
  HotA/HD log is rebuilt from a second cache that observes append chronology,
  not from the already-rotated native vector.
- `Patch_v2.6_VISUAL_TEST13` therefore defers only mass-Cure resurrection log
  calls at `0x005A7A3F`. It stores the creature id and revived count, lets the
  native Cure line append normally, then recreates the original localized
  messages and appends them through native `0x004729D0`. Single Cure and
  ordinary Resurrection tail-jump directly to the original logger.
- Runtime testing confirmed TEST13: mass Cure now appends the Cure cast line
  before every revival line, with no regression in resurrection quantity,
  animation, sound, permanence, or stability. TEST13 was promoted byte-for-byte
  to formal `Patch_v2.6`.
- LOGDIAG01 keeps the accepted Stage 3 gameplay bytes and routes only Cure-triggered
  resurrection calls through a scoped visual flag.
- Native resurrection state updates, corpse placement, permanence, and the
  resurrection combat-log path remain before the visual gate.
- TEST4 preserves the valid Resurrection effect object, writes an out-of-range
  public frame index only during Cure-triggered stand-up redraws, and bypasses
  only the Resurrection sound call. It keeps the creature's native stand-up
  frames and the original Cure presentation/sound. Ordinary Resurrection uses
  the original frame index, sound, circle effect, and stand-up path throughout.
- TEST4 runs the reverse death animation for `N+1` iterations. The added final
  iteration reaches the original `0x005A7B3D` transition from animation group 5
  to standing group 2 instead of leaving the creature on group 5 frame zero.
- The scoped flag is cleared at the native public cleanup entry, including the
  autoresolve/no-animation branch.
- Formal `HOTA_NEW_HERO_V1` kept the tested Cure/Elf runtime implementation,
  restores Adela to native HotA 1.8.0 mana cost, removes the custom Adela line
  from both HeroSpec archives, and presents Cure as the added resurrection
  sentence followed by the original `(8-n)` scaling sentence.

V1.2 first-active-attack development:

- `FIRSTATTACK_DIAG03` captured 38 calls from the two true HotA.dll physical
  attack callbacks and proved that original argument 2 is the attacking stack.
  Static HotA 1.8.0 disassembly independently confirmed `stack+0x70` as the
  native lucky-strike flag and showed that both callbacks clear it at the end
  of a hit.
- `FIRSTATTACK_DIAG04` captured 25 attack calls. Its `activeStack` candidate was
  null throughout and was rejected. The EXE action dispatch table instead
  proves that ranged action 6 enters at `0x00478D70` and melee action 7 enters
  at `0x00478B94`, with `EBX` holding the active stack before any retaliation
  or repeated-hit callbacks occur.
- `HOTA_NEW_HERO_V1.2_FIRSTATTACK_TEST1` failed functional testing even though
  its log proved the action qualification, per-stack consumption, specialist
  gate, and attacker matching were correct. The callback changed `isLucky`
  from 0 to 1, but did so before HotA's true Luck roll overwrote the flag.
- Static tracing then located HotA's actual Luck function at preferred VA
  `0x10133880`; its native success path writes `stack+0x70=1` at `0x101338DD`
  and continues through the normal animation, sound, combat-log and damage
  path. `HOTA_NEW_HERO_V1.2_FIRSTATTACK_TEST2` hooks this function entry. The
  user confirmed all tested attack types work and approved formal release. The
  proven action 6/7 bookkeeping and post-hard-disable side gate remain
  unchanged, so retaliation cannot consume
  or inherit the guarantee and Hourglass/Cursed Ground still take priority.
- Formal `HOTA_NEW_HERO_V1.12` combines the accepted V1.11 fixed-Luck `+3`
  return with the accepted TEST2 first-active-attack path. Its formal payload
  removes all binary diagnostic-file writing. Two deterministic builds,
  independent verification, runtime fixed-`+3` and HotA Luck-hook inspection,
  and both standard/HD startup gates passed. Future work must use V1.12 as the
  release baseline, never TEST1/TEST2 or any diagnostic package.
- Formal `HOTA_NEW_HERO_V1.13` uses V1.12 as its sole source and changes only
  Daremyth's starting-spell dword at EXE file offset `0x0027AD64` from Mirth
  (`31 00 00 00`) to Magic Arrow (`0F 00 00 00`), plus each EXE checksum and
  the root installation text. The full Daremyth record, skills, spellbook flag,
  rollback bytes, package member set, and all non-EXE gameplay files are
  verified. It is the sole formal source used to build V1.14.
- Formal `HOTA_NEW_HERO_V1.14` uses V1.13 as its sole source. In both EXEs it
  changes Melodia `record + 0x14` from Mysticism (`08 00 00 00`) to Leadership
  (`06 00 00 00`) and Daremyth `record + 0x20` from Magic Arrow
  (`0F 00 00 00`) to View Air (`05 00 00 00`), plus each PE checksum and the
  root installation text. All other bytes and gameplay paths are preserved.
  V1.14 is the sole source used to build formal V1.2. Future work must use
  formal V1.2 as the release baseline.

## Non-negotiable rules

1. Prove the runtime execution path before patching gameplay logic.
2. Static byte insertion is not proof that a hook executes.
3. Analyze `h3hota.exe`, `h3hota HD.exe`, `HotA.dll`, `HD_HOTA.dll`, `HW_HOTA.dll`, and `patcher_x86` where available.
4. Treat H3API addresses as search hints only, not as verified HotA 1.8.0 runtime addresses.
5. Map all existing Patch_v1.8 binary changes before allocating a code cave or PE section.
6. Preserve registers, flags, stack balance, calling convention, and original instructions.
7. Do not manually edit `numberAlive`, `healthLost`, or `numberForeverDead` if the native resurrection function can perform the operation.
8. Do not use negative `healthLost`.
9. Do not use an external `temporaryHP` array.
10. Do not reinterpret unused HeroSpec fields.
11. Do not maintain a custom undead/elemental/construct blacklist. Reuse native Resurrection target validation.
12. Build and analyze standard and HD executables independently.
13. Produce a diagnostic hook first. The user must confirm a runtime log before resurrection logic is added.
14. Never claim success from PE checks, ZIP integrity, disassembly, or static signatures alone.
15. Every build must include input hashes, output hashes, changed offsets, original bytes, patched bytes, and rollback bytes.
16. Never overwrite a release payload in place; each later release receives a new versioned filename and SHA-256.
17. Never allocate a code cave from a zero run without checking adjacent strings,
    terminators, tables, and startup data; preserve every semantic boundary byte.
18. A distributed test build must pass a real startup-to-main-menu smoke test; static
    PE, disassembly, and hash checks alone do not establish that it starts.

## Preserve existing Patch_v1.8 behavior

- Elf Queen in Aenain slot: Pixie/Sprite +1 damage and +1 speed.
- Elf Queen starts with 25/25/25 Pixies.
- Elf Queen uses the Planeswalker class, starts with primary stats 3/1/1/1
  (Attack/Defense/Power/Knowledge), and has Basic Tactics + Basic Offense.
- Ivor starts with 12–24 Centaurs and 6 + 6 Wood Elves.
- Other heroes use HotA 1.8.0 starting-army ranges.
- Adela is fully native HotA 1.8.0; Bless uses the original mana cost and no
  custom Adela behavior or README section may be reintroduced.
- Melodia and Daremyth return final Luck `+3` after native hard-disable gates.
  Hourglass of the Evil Hour, Cursed Ground, and equivalent native disable
  effects remain effective. Melodia starts with Basic Wisdom + Basic Leadership
  and Mirth; Daremyth keeps Basic Wisdom + Basic Intelligence and starts with
  View Air in her spell book.
- Solmyr and Loynis remain at native HotA 1.8.0 behavior.
- Coronius keeps Basic Wisdom + Basic Scholar and starts with Slayer. His old
  native Slayer specialty is disabled; the accepted Scholar contribution and
  bilateral Wisdom-cap bonuses replace it, with the native level-5 ceiling.
- Preserve D32F 215-frame UN44/UN32 files and Elf Queen frame 141.

## Required deliverables before gameplay patching

- `analysis/baseline_diff.md`
- `analysis/cure_runtime_path.md`
- `analysis/existing_patch_map.json`
- a diagnostic-only build that logs execution of the real Uland/Astra hero-cast Cure path

## Release naming

- After V1, adding a new hero or a new hero specialty increases the version by
  `0.1`; a numerical adjustment to existing content increases it by `0.01`.
- V1.01 was the first numerical-adjustment release under this rule, but was
  withdrawn. V1.02 corrected it; V1.03 and V1.04 are subsequent numerical/data
  adjustments.

- Diagnostic builds: `Patch_v2.4_diagNN`
- User Stage 2 test: `Patch_v2.4_STAGE2_TEST`
- Withdrawn Stage 3 corpse test: `Patch_v2.5_STAGE3_TEST` (startup-broken; forensics only)
- Withdrawn Stage 3 corpse retest: `Patch_v2.5_STAGE3_TEST2` (single target blocked; forensics only)
- User Stage 3 single-target retest: `Patch_v2.5_STAGE3_TEST3`
- Formal Stage 3 release: `Patch_v2.5`
- Stage 4 Cure-animation isolation test: `Patch_v2.6_VISUAL_TEST1`
- Stage 4 circle/stand-up split retest: `Patch_v2.6_VISUAL_TEST2`
- Stage 4 valid-object/soundless retest: `Patch_v2.6_VISUAL_TEST3`
- Stage 4 native stand-up completion retest: `Patch_v2.6_VISUAL_TEST4`
- Stage 4 Cure combat-log ordering retest: `Patch_v2.6_VISUAL_TEST5`
- Withdrawn Stage 4 two-phase mass Cure retest: `Patch_v2.6_VISUAL_TEST6`
- Withdrawn Stage 4 post-settlement combat-log rotation retest: `Patch_v2.6_VISUAL_TEST7`
- Stage 4 TEST4-layout-preserving log rotation retest: `Patch_v2.6_VISUAL_TEST8`
- Stage 4 mandatory-init log rotation retest: `Patch_v2.6_VISUAL_TEST9`
- Stage 4 mandatory-runtime-path log rotation retest: `Patch_v2.6_VISUAL_TEST10`
- Stage 4 observable-native-call log rotation retest: `Patch_v2.6_VISUAL_TEST11`
- Stage 4 native Cure logger post-append rotation retest: `Patch_v2.6_VISUAL_TEST12`
- Stage 4 one-run binary log-path diagnostic: `Patch_v2.6_VISUAL_LOGDIAG01`
- Historical formal Stage 4 release: `Patch_v2.6`
- Historical formal release: `HOTA_NEW_HERO_V1`
- Withdrawn numerical release: `HOTA_NEW_HERO_V1.01`
- Historical numerical release: `HOTA_NEW_HERO_V1.02`
- Historical numerical release: `HOTA_NEW_HERO_V1.03`
- Historical numerical release: `HOTA_NEW_HERO_V1.04`
- Historical numerical release: `HOTA_NEW_HERO_V1.05`
- Historical numerical release: `HOTA_NEW_HERO_V1.06`
- Historical formal specialty release: `HOTA_NEW_HERO_V1.1`
- Historical formal specialty release: `HOTA_NEW_HERO_V1.12`
- Historical formal balance release: `HOTA_NEW_HERO_V1.13`
- Historical formal balance release: `HOTA_NEW_HERO_V1.14`
- Current formal specialty release: `HOTA_NEW_HERO_V1.2`
- Do not reuse historical version numbers.

## GitHub release layout

- Keep Chinese, English, and copyright content in mutually exclusive, same-page `<details name="section">` panels in the root `README.md`; all three panels are collapsed by default.
- The README must contain exactly six hero sections per language: Elf Queen,
  Coronius, Melodia, Daremyth, Uland, and Astra. Each hero keeps the common fields: hero
  name, a local portrait immediately beneath the name, biography, specialty
  effect, starting army, initial profile (class plus
  Attack/Defense/Power/Knowledge), and starting skills. Render every portrait
  from `assets/portraits/` at a height of 72 pixels. On the same line, follow it
  with four nonbreaking spaces and that hero's 72-pixel-high specialty icon
  from `assets/specialties/`. For every hero whose record has a spellbook,
  follow the specialty with twelve nonbreaking spaces and the 72-pixel-high
  native spellbook icon from `assets/spellbook/`, then four nonbreaking spaces
  and the 72-pixel-high current starting-spell icon from `assets/spells/`.
  Elf Queen's current record has no spellbook and must not display those two
  icons. Elf Queen keeps an individual creative direction;
  grouped Luck and Cure heroes use the group-level creative-direction fields
  described below. Adela must not appear in the landing README.
- Store README specialty PNGs in their final upright orientation. Specialty
  frames exported from the current D32F `UN44.DEF` require a 180-degree
  correction before publication; do not publish the raw inverted orientation.
- Render `Creative Direction`, `Additional Note`, and `Current Cure Formula`
  content as level-three headings followed by ordinary paragraphs. Do not add
  labels such as “shared by both heroes”; group placement already communicates
  the scope.
- In each language panel, place Melodia and Daremyth together beneath one
  horizontal divider and one Luck-specialty group heading. Each individual
  specialty effect states only fixed Luck `+3`. After both heroes, provide one
  group-level additional note for native hard-disable effects such as Hourglass
  of the Evil Hour and Cursed Ground, followed by one group-level creative
  direction.
- In each language panel, place Uland and Astra together beneath one horizontal
  divider and one Cure-specialty group heading. After both heroes, provide one
  group-level creative direction, then show the current Cure formula. Every
  numerical Cure update must update both README formulas to match the release
  manifest in the same commit.
- Show one bilingual large title and one bilingual expansion hint above the three
  collapsed panels. Do not restore the old badge/button row.
- Keep a direct current-ZIP download link inside both language panels rather than
  linking to the `Download/` directory or a GitHub file-preview page.
- Do not retain diagnostic ZIPs, extracted test packages, failed binaries, raw
  runtime logs, or test manifests in the published repository.
- Keep only the newest formal patch and its release metadata in `Download/`.
- `OLD/` contains only `Patch_v1.8.zip` and its explanation. Superseded later
  formal packages are removed after their SHA-256 and conclusions are logged.
- Every formal change and every diagnostic/test attempt must leave a Markdown
  log under `CHANGELOG/` describing the change, result, error, and lesson.
- Do not overwrite an older package with a new payload. Preserve versioned filenames and SHA-256 values.
