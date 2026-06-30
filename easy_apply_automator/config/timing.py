"""Defines centralized timing and pause duration constants used across the bot."""

from __future__ import annotations

# Centralized sleep durations (in seconds)

# Progress bar checks and quick element checking loops
POLL_INTERVAL_SECONDS = 0.05

# Very quick actions or redirect cooldowns
MICRO_PAUSE_SECONDS = 0.1

# Cooldown between state machine loops
STATE_MACHINE_PAUSE_SECONDS = 0.15

# Delay after scrolling and clicking elements
CLICK_PAUSE_SECONDS = 0.2

# Delay for dropdown/typeahead options rendering
TYPEAHEAD_PAUSE_SECONDS = 0.4

# Cooldown for modal transitions or lock screen updates
MODAL_TRANSITION_PAUSE_SECONDS = 0.5

# Generic wait for question processing elements rendering
QUESTION_LOAD_PAUSE_SECONDS = 1.0

# General page loading or security verification delays
PAGE_LOAD_PAUSE_SECONDS = 2.0
