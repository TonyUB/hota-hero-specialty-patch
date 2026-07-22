# AGENTS.md — HotA 1.8.0 Binary Patch Project

## Trusted baseline

- The only trusted modified baseline is `Patch_v1.8.zip`.
- Never build on Patch_v1.9, v2.0, v2.1, v2.2, or v2.3.
- Historical test packages and failed binaries are no longer retained in the
  repository. Their conclusions are preserved under `CHANGELOG/` and `analysis/`.
- `Download/HOTA_NEW_HERO_V1.02.zip` is the current formal release.

## Current milestone

Stage 4 is the current stable release. All Stage 3 gameplay gates and Stage 4
presentation/log-order gates passed:

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
- `Download/HOTA_NEW_HERO_V1.02.zip` inherits the runtime-accepted V1 Cure,
  presentation, log-order, and Elf implementation. V1.02 corrects only the
  Uland/Astra Cure specialty arithmetic and release documentation; its new
  arithmetic still requires an in-game value check.
- Astra starting skills remain Basic Wisdom + Basic Water Magic.
- V1.02 Cure uses, at every Water Magic mastery,
  `H = 10P + 30 + floor((20P + 60) * 3(L - 1) / (3L + 16 - n))`.
  At `P=1, L=1`, the result is always 40 regardless of target tier. Water Magic
  controls only native single-target versus mass-target casting and does not
  change the numeric result. Both living and fully dead specialist targets
  finish at the same custom total; non-specialists tail-call the original bonus
  function.
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
- Melodia, Solmyr, and Loynis remain at native HotA 1.8.0 behavior.
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
  withdrawn. V1.02 is its corrected replacement.

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
- Current formal release: `HOTA_NEW_HERO_V1.02`
- Do not reuse historical version numbers.

## GitHub release layout

- Keep Chinese, English, and copyright content in mutually exclusive, same-page `<details name="section">` panels in the root `README.md`; all three panels are collapsed by default.
- The README must contain exactly three hero sections per language: Elf Queen,
  Uland, and Astra. Each uses the same template: hero name, biography, specialty
  effect, starting army, initial profile (class plus Attack/Defense/Power/Knowledge),
  starting skills, and creative direction. Adela must not appear in the landing README.
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
