"""
Unit tests for Room creation validation and parameter constraints.

Since RoomService.create_room performs async I/O, these tests focus on the
Room *model* validation that create_room relies on, plus boundary checks.
"""

import pytest
from models.room import Room
from config import (
    MIN_PLAYERS, MAX_PLAYERS, MIN_SPY_COUNT, MAX_SPY_RATIO,
    MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME,
)


class TestRoomCreationConstraints:

    def test_minimum_players(self):
        room = Room.create_room("R", "usr_host123456", total_players=MIN_PLAYERS)
        assert room.total_players == MIN_PLAYERS

    def test_maximum_players(self):
        room = Room.create_room("R", "usr_host123456", total_players=MAX_PLAYERS)
        assert room.total_players == MAX_PLAYERS

    def test_spy_count_minimum(self):
        room = Room.create_room("R", "usr_host123456", spy_count=MIN_SPY_COUNT)
        assert room.spy_count == MIN_SPY_COUNT

    def test_spy_ratio_within_bounds(self):
        """Verify that a reasonable spy count passes the ratio check."""
        total = 6
        spy = 2
        assert spy / total <= MAX_SPY_RATIO
        room = Room.create_room("R", "usr_host123456", total_players=total, spy_count=spy)
        assert room.spy_count == spy

    def test_spy_ratio_exceeds_bound(self):
        """Application layer should reject this; model stores raw value."""
        total = 3
        spy = 2  # 66% > MAX_SPY_RATIO (40%)
        assert spy / total > MAX_SPY_RATIO

    def test_max_rounds_upper_bound(self):
        room = Room.create_room("R", "usr_host123456", max_rounds=MAX_ROUNDS)
        assert room.max_rounds == MAX_ROUNDS

    def test_speak_time_upper_bound(self):
        room = Room.create_room("R", "usr_host123456", speak_time=MAX_SPEAK_TIME)
        assert room.speak_time == MAX_SPEAK_TIME

    def test_last_words_time_upper_bound(self):
        room = Room.create_room("R", "usr_host123456", last_words_time=MAX_LAST_WORDS_TIME)
        assert room.last_words_time == MAX_LAST_WORDS_TIME


class TestRoomInviteCodeUniqueness:

    def test_generated_codes_differ(self):
        """Two independently created rooms should (almost certainly) have different codes."""
        codes = {Room.create_room("R", "h").invite_code for _ in range(50)}
        assert len(codes) == 50


class TestRoomDictSerialization:

    def test_none_values_preserved(self):
        room = Room.create_room("R", "usr_host123456")
        d = room.dict()
        assert d["god_id"] is None
        assert d["word_civilian"] is None

    def test_numeric_fields_remain_numeric(self):
        room = Room.create_room("R", "usr_host123456", total_players=5, spy_count=2)
        d = room.dict()
        assert isinstance(d["total_players"], int)
        assert isinstance(d["spy_count"], int)

    def test_boolean_fields_are_string(self):
        room = Room.create_room("R", "usr_host123456", is_public=False)
        d = room.dict()
        assert d["is_public"] == "false"
