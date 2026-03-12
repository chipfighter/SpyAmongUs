"""
Unit tests for configuration defaults and constants.
"""

import config


class TestRedisConfig:

    def test_redis_host_has_default(self):
        assert isinstance(config.REDIS_HOST, str)

    def test_redis_port_is_int(self):
        assert isinstance(config.REDIS_PORT, int)

    def test_redis_db_is_int(self):
        assert isinstance(config.REDIS_DB, int)


class TestMongoConfig:

    def test_mongodb_url_starts_with_scheme(self):
        assert config.MONGODB_URL.startswith("mongodb")

    def test_mongodb_dbname_is_set(self):
        assert len(config.MONGODB_DBNAME) > 0


class TestAppConfig:

    def test_app_port_is_int(self):
        assert isinstance(config.APP_PORT, int)

    def test_debug_is_bool(self):
        assert isinstance(config.DEBUG, bool)


class TestJWTConfig:

    def test_algorithm_is_hs256(self):
        assert config.JWT_ALGORITHM == "HS256"

    def test_access_token_expiry_positive(self):
        assert config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES > 0

    def test_refresh_token_expiry_positive(self):
        assert config.JWT_REFRESH_TOKEN_EXPIRE_DAYS > 0


class TestGameConstants:

    def test_player_bounds(self):
        assert config.MIN_PLAYERS >= 2
        assert config.MAX_PLAYERS >= config.MIN_PLAYERS

    def test_spy_count_minimum(self):
        assert config.MIN_SPY_COUNT >= 1

    def test_max_spy_ratio_less_than_one(self):
        assert 0 < config.MAX_SPY_RATIO < 1

    def test_max_rounds_positive(self):
        assert config.MAX_ROUNDS > 0

    def test_speak_time_positive(self):
        assert config.MAX_SPEAK_TIME > 0

    def test_last_words_time_positive(self):
        assert config.MAX_LAST_WORDS_TIME > 0

    def test_vote_timeout_positive(self):
        assert config.VOTE_TIMEOUT > 0


class TestRoleConstants:

    def test_roles_are_distinct(self):
        roles = {config.ROLE_CIVILIAN, config.ROLE_SPY, config.ROLE_GOD}
        assert len(roles) == 3


class TestGamePhaseConstants:

    def test_phases_are_distinct(self):
        phases = {
            config.GAME_PHASE_SPEAKING,
            config.GAME_PHASE_VOTING,
            config.GAME_PHASE_LAST_WORDS,
            config.GAME_PHASE_SECRET_CHAT,
        }
        assert len(phases) == 4


class TestRedisKeyPrefixes:

    def test_user_key_prefix(self):
        assert "user:" in config.USER_KEY_PREFIX

    def test_room_key_prefix(self):
        assert "room:" in config.ROOM_KEY_PREFIX

    def test_room_users_key_is_template(self):
        assert "%s" in config.ROOM_USERS_KEY_PREFIX
