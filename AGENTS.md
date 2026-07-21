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
- Do not reuse historical version numbers.

## GitHub release layout

- Keep Chinese and English in mutually exclusive, same-page `<details name="language">` panels in the root `README.md`; Chinese is open by default and neither language control may navigate to another page.
- The README must contain only three in-game hero sections per language: Elf Queen; Uland/Astra; Adela. Use the in-game biography followed directly by the specialty effect; include only Elf Queen's 25/25/25 starting army and omit unrelated engineering details.
- The Download button must point directly to the current ZIP rather than to the `Download/` directory or a GitHub file-preview page.
- Store diagnostic and gameplay test packages, their instructions, and their manifests in `TEST/`.
- Keep only the newest formal patch and its release metadata in `Download/`.
- Before promoting a new formal patch, move the complete previous formal release from `Download/` to `OLD/`; never place test builds in `OLD/`.
- Do not overwrite an older package with a new payload. Preserve versioned filenames and SHA-256 values.
