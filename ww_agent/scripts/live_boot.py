#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Compatibility entrypoint for the bounded one-resident runner.

Prefer the repository-level command because it also verifies Docker topology and
that the selected city's cohort service is stopped:

    python dev.py resident --city ww_sfo --resident NAME
"""

from __future__ import annotations

from resident_once import main

if __name__ == "__main__":
    raise SystemExit(main())
