# AGENTS.md — HotA 1.8.0 Binary Patch Project

## Trusted baseline

- The only trusted modified baseline is `Patch_v1.8.zip`.
- Never build on Patch_v1.9, v2.0, v2.1, v2.2, or v2.3.
- Later cure/resurrection packages are failed or unverified experiments and are for forensics only.

## Current milestone

Implement only Stage 2:

- Uland and Astra cast Cure on a stack that still has at least one living creature.
- Preserve native Cure and native specialty scaling.
- Normal healing is applied first.
- Remaining healing points permanently resurrect casualties in the same stack.
- Use native Resurrection eligibility restrictions.
- Do not support fully dead corpse targets yet.
- Do not scan fully dead stacks during Expert Water Magic mass Cure yet.
- Astra starting skills must become Basic Wisdom + Basic Water Magic.

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
- Do not reuse historical version numbers.

## GitHub release layout

- Keep Chinese and English in mutually exclusive, same-page `<details name="language">` panels in the root `README.md`; Chinese is open by default and neither language control may navigate to another page.
- The README must contain only three in-game hero sections per language: Elf Queen; Uland/Astra; Adela. Use the in-game biography followed directly by the specialty effect; include only Elf Queen's 25/25/25 starting army and omit unrelated engineering details.
- The Download button must point directly to the current ZIP rather than to the `Download/` directory or a GitHub file-preview page.
- Store diagnostic and gameplay test packages, their instructions, and their manifests in `TEST/`.
- Keep only the newest formal patch and its release metadata in `Download/`.
- Before promoting a new formal patch, move the complete previous formal release from `Download/` to `OLD/`; never place test builds in `OLD/`.
- Do not overwrite an older package with a new payload. Preserve versioned filenames and SHA-256 values.
