#!/usr/bin/env python3
"""Verify UIDIAG02 using the independent UIDIAG verifier."""

from __future__ import annotations

import build_hota_new_hero_v106_uidiag02 as diag02
import verify_hota_new_hero_v106_uidiag01 as verifier


def main() -> int:
    verifier.BUILD_NAME = diag02.BUILD_NAME
    verifier.build_payload = diag02.build_payload
    return verifier.main()


if __name__ == "__main__":
    raise SystemExit(main())
