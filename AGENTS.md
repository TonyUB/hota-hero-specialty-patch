# AGENTS.md — HotA 1.8.0 Binary Patch Project

## Trusted baseline

- The only trusted modified baseline is `Patch_v1.8.zip`.
- Never build on Patch_v1.9, v2.0, v2.1, v2.2, or v2.3.
- Historical cure/resurrection test packages remain test or forensic inputs; only
  `Download/Patch_v2.5.zip` is the current accepted formal release.

## Current milestone

Stage 3 is the current stable release. All required TEST3 runtime gates passed:

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
- `Download/Patch_v2.5.zip` is the accepted formal release. Preserve its tested
  executable bytes unless a later feature explicitly requires a new runtime gate.
- Astra starting skills remain Basic Wisdom + Basic Water Magic.

Stage 4 is an experimental visual-only follow-up:

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
- `TEST/Patch_v2.6_VISUAL_TEST6.zip` supersedes TEST5. Single Cure keeps the
  accepted TEST5 ordering. Mass Cure now validates and premarks living/dead
  targets, calls the original cast-message routine only after the affected
  table is complete, and then applies Cure/permanent resurrection in a second
  phase.
- TEST6 keeps the accepted Stage 3 gameplay bytes and routes only Cure-triggered
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
- Do not promote TEST6 or replace `Download/Patch_v2.5.zip` until the user
  confirms the Cure cast line appears before every revival line in both single
  and mass Cure, while the already accepted TEST4 behavior remains unchanged.

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
16. Keep the accepted `Download/Patch_v2.5.zip` unchanged until a later formal release replaces it.
17. Never allocate a code cave from a zero run without checking adjacent strings,
    terminators, tables, and startup data; preserve every semantic boundary byte.
18. A distributed test build must pass a real startup-to-main-menu smoke test; static
    PE, disassembly, and hash checks alone do not establish that it starts.

## Preserve existing Patch_v1.8 behavior

- Elf Queen in Aenain slot: Pixie/Sprite +1 damage and +1 speed.
- Elf Queen starts with 25/25/25 Pixies.
- Ivor starts with 12–24 Centaurs and 6 + 6 Wood Elves.
- Other heroes use HotA 1.8.0 starting-army ranges.
- Adela retains native Bless specialty and casts Bless for 0 mana only.
- Melodia, Solmyr, and Loynis remain at native HotA 1.8.0 behavior.
- Preserve D32F 215-frame UN44/UN32 files and Elf Queen frame 141.

## Required deliverables before gameplay patching

- `analysis/baseline_diff.md`
- `analysis/cure_runtime_path.md`
- `analysis/existing_patch_map.json`
- a diagnostic-only build that logs execution of the real Uland/Astra hero-cast Cure path

## Release naming

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
- Stage 4 safe two-phase mass Cure retest: `Patch_v2.6_VISUAL_TEST6`
- Future formal Stage 4 release after runtime acceptance: `Patch_v2.6`
- Do not reuse historical version numbers.

## GitHub release layout

- Keep Chinese and English in mutually exclusive, same-page `<details name="language">` panels in the root `README.md`; Chinese is open by default and neither language control may navigate to another page.
- The README must contain only three in-game hero sections per language: Elf Queen; Uland/Astra; Adela. Use the in-game biography followed directly by the specialty effect; include only Elf Queen's 25/25/25 starting army and omit unrelated engineering details.
- The Download button must point directly to the current ZIP rather than to the `Download/` directory or a GitHub file-preview page.
- Store diagnostic and gameplay test packages, their instructions, and their manifests in `TEST/`.
- Keep only the newest formal patch and its release metadata in `Download/`.
- Before promoting a new formal patch, move the complete previous formal release from `Download/` to `OLD/`; never place test builds in `OLD/`.
- Do not overwrite an older package with a new payload. Preserve versioned filenames and SHA-256 values.
