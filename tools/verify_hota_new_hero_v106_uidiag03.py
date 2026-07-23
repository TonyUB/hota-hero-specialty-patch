#!/usr/bin/env python3
"""Verify UIDIAG03 using the independent isolated-section verifier."""

from __future__ import annotations

import build_hota_new_hero_v106_uidiag03 as diag03
import verify_hota_new_hero_v106_uidiag01 as verifier


def main() -> int:
    verifier.BUILD_NAME = diag03.BUILD_NAME
    verifier.NATIVE_EFFECT_VA = diag03.SPRINTF_VA
    verifier.NATIVE_EFFECT_ORIGINAL = diag03.SPRINTF_ORIGINAL
    verifier.WRAPPER_VA = diag03.WRAPPER_VA
    verifier.build_payload = diag03.build_payload
    return verifier.main()


if __name__ == "__main__":
    raise SystemExit(main())
