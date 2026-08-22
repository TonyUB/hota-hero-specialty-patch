# HOTA_NEW_HERO_V1.5 Manifest

- Release date: 2026-08-22
- ZIP: `HOTA_NEW_HERO_V1.5.zip`
- Size: `22,699,132` bytes
- Members: `27`
- SHA-256: `0e4694c051d6156bb0c9e8373fcdbf8cf56a5750202000c1dc0ab0d8e23965a0`
- Hero: 奥蕾加 / Olega, Stronghold Battle Mage, hero ID 110
- Starting skills: Basic Wisdom + Basic Scouting
- Starting spell: View Air / 观天, spell ID 5
- Starting army: 20–30 Goblins + 5–7 Wolf Riders + 5–6 Orcs
- Primary skills: Attack 2 / Defense 1 / Power 1 / Knowledge 1
- Specialty: Treasure Hunt / 寻宝术
- Dig threshold: at least 100 current movement points
- Previous public baseline retained in `OLD/`: V1.4, SHA-256 `effc379e756bb5f41d56580fb329b54e2c122730effcea3a0189b7235216e9ba`

Independent verification passed for both EXEs, PE checksums, the three movement gates, native Eagle Eye disable, starting spell, synchronized language resources, 215-frame atlas isolation, standard loose ZSoft PCX portraits, frozen DLL/DAT members, ZIP CRC, rollback reconstruction, and deterministic double build.

This same-version hotfix supersedes SHA-256 `de61ee100071dfef38679c41738ae59b2ead099fa6f8d845f066262a0e0a5a07`. It remaps only three marked portrait pixels away from reserved palette index 0, compensates the treasure-chest icon's observed in-game horizontal mirroring, and completes the bilingual landing profile.
