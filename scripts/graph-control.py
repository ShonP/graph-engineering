#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.2"]
# ///
"""Pinned entry point for deterministic Graph Engineering controls."""

from graph_control.cli import main

raise SystemExit(main())
