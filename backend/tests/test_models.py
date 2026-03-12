"""
Unit tests for Pydantic data models: User, Room, Message.
"""

import time
from models.user import User, UserStatistics, StyleProfile
from models.room import Room
from models.message import Message
from config import (
    USER_STATUS_ONLINE, GAME_STATUS_WAITING,
    MIN_PLAYERS, MIN_SPY_COUNT, MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME,
)


# ── User ──────────────────────────────────────────────────────────────────

class TestUserModel:

    def test_create_user_generates_id(self):
        user = User.create_user("alice", "password123")
        assert user.id.startswith("usr_")
        assert len(user.id) == 16  # "usr_" + 12 hex chars

    def test_create_user_hashes_password(self):
        user = User.create_user("bob", "s3cret")
        assert user.password_hash is not None
        assert user.salt is not None
        assert user.password_hash != "s3cret"

    def test_verify_password_correct(self):
        user = User.create_user("carol", "mypassword")
        assert user.verify_password("mypassword") is True

    def test_verify_password_incorrect(self):
        user = User.create_user("dave", "right")
        assert user.verify_password("wrong") is False

    def test_verify_password_returns_false_when_no_hash(self):
        user = User(id="usr_test", username="nohash")
        assert user.verify_password("anything") is False

    def test_hash_password_deterministic_with_salt(self):
        h1, s1 = User.hash_password("pw", salt="fixedsalt")
        h2, s2 = User.hash_password("pw", salt="fixedsalt")
        assert h1 == h2
        assert s1 == s2

    def test_hash_password_generates_salt_when_omitted(self):
        h1, s1 = User.hash_password("pw")
        h2, s2 = User.hash_password("pw")
        assert s1 != s2  # random salts differ

    def test_default_statistics(self):
        user = User.create_user("eve", "pw")
        assert user.statistics.total_games == 0
        assert user.statistics.win_rate == 0.0

    def test_default_style_profile(self):
        user = User.create_user("frank", "pw")
        assert user.style_profile.summary == ""
        assert user.style_profile.tags == set()

    def test_dict_excludes_sensitive_fields(self):
        user = User.create_user("grace", "pw")
        d = user.dict()
        assert "password_hash" not in d
        assert "salt" not in d
        assert "username" in d

    def test_default_status_is_online(self):
        user = User.create_user("heidi", "pw")
        assert user.status == USER_STATUS_ONLINE

    def test_admin_defaults_to_false(self):
        user = User.create_user("ivan", "pw")
        assert user.is_admin is False
        assert user.is_muted is False
        assert user.is_banned is False


# ── UserStatistics ────────────────────────────────────────────────────────

class TestUserStatistics:

    def test_defaults(self):
        stats = UserStatistics()
        assert stats.total_games == 0
        assert stats.win_rates == {"civilian": 0.0, "spy": 0.0}

    def test_custom_values(self):
        stats = UserStatistics(total_games=10, win_count=7, win_rate=0.7)
        assert stats.total_games == 10
        assert stats.win_rate == 0.7


# ── StyleProfile ──────────────────────────────────────────────────────────

class TestStyleProfile:

    def test_defaults(self):
        sp = StyleProfile()
        assert sp.summary == ""
        assert isinstance(sp.tags, set)

    def test_with_tags(self):
        sp = StyleProfile(tags={"aggressive", "bluffer"})
        assert "aggressive" in sp.tags


# ── Room ──────────────────────────────────────────────────────────────────

class TestRoomModel:

    def test_create_room_generates_invite_code(self):
        room = Room.create_room("TestRoom", "usr_host123456")
        assert len(room.invite_code) == 8
        assert room.invite_code.isalnum()

    def test_create_room_defaults(self):
        room = Room.create_room("TestRoom", "usr_host123456")
        assert room.total_players == MIN_PLAYERS
        assert room.spy_count == MIN_SPY_COUNT
        assert room.max_rounds == MAX_ROUNDS
        assert room.speak_time == MAX_SPEAK_TIME
        assert room.last_words_time == MAX_LAST_WORDS_TIME
        assert room.status == GAME_STATUS_WAITING
        assert room.god_id is None

    def test_create_room_custom_params(self):
        room = Room.create_room(
            "Custom", "usr_host123456",
            is_public=False,
            total_players=6,
            spy_count=2,
            max_rounds=5,
            speak_time=30,
            last_words_time=20,
            llm_free=True,
        )
        assert room.is_public is False
        assert room.total_players == 6
        assert room.spy_count == 2
        assert room.llm_free is True

    def test_dict_converts_booleans_to_lowercase_strings(self):
        room = Room.create_room("BoolRoom", "usr_host123456", is_public=True)
        d = room.dict()
        assert d["is_public"] == "true"
        assert d["llm_free"] == "false"
        assert d["secret_chat_active"] == "false"

    def test_timestamps_are_set(self):
        before = int(time.time() * 1000)
        room = Room.create_room("TimeRoom", "usr_host123456")
        after = int(time.time() * 1000)
        assert before <= room.created_at <= after
        assert before <= room.last_active <= after


# ── Message ───────────────────────────────────────────────────────────────

class TestMessageModel:

    def test_create_user_message(self):
        msg = Message.create_user_message("usr_001", "Alice", "Hello!")
        assert msg.user_id == "usr_001"
        assert msg.username == "Alice"
        assert msg.content == "Hello!"
        assert msg.is_system is False
        assert msg.round == "0"

    def test_create_system_message(self):
        msg = Message.create_system_message("Game started")
        assert msg.user_id == "system"
        assert msg.username == "System"
        assert msg.is_system is True
        assert msg.content == "Game started"

    def test_message_timestamp_is_recent(self):
        before = int(time.time() * 1000)
        msg = Message.create_user_message("u1", "U", "hi")
        after = int(time.time() * 1000)
        assert before <= msg.timestamp <= after

    def test_mentions_default_empty(self):
        msg = Message.create_user_message("u1", "U", "hi")
        assert msg.mentions == []

    def test_ai_type_default_none(self):
        msg = Message.create_user_message("u1", "U", "hi")
        assert msg.ai_type is None
