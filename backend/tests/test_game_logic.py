"""
Unit tests for GameService game logic (vote tallying, win conditions, etc.).

These tests mock Redis so no running database is required.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from services.game_service import GameService
from config import ROLE_CIVILIAN, ROLE_SPY, ROLE_GOD


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def game_service(mock_redis_client, mock_websocket_manager):
    svc = GameService(
        redis_client=mock_redis_client,
        websocket_manager=mock_websocket_manager,
    )
    return svc


# ---------------------------------------------------------------------------
# tally_votes
# ---------------------------------------------------------------------------

class TestTallyVotes:

    @pytest.mark.asyncio
    async def test_clear_winner(self, game_service, mock_redis_client):
        """One player receives the majority of votes."""
        mock_redis_client.get_room_basic_data.return_value = {"current_round": "1"}
        mock_redis_client.hgetall.return_value = {
            "usr_a": "usr_c",
            "usr_a_time": "2.1",
            "usr_b": "usr_c",
            "usr_b_time": "3.0",
            "usr_c": "usr_a",
            "usr_c_time": "1.5",
        }

        result = await game_service.tally_votes("ROOM1234")
        assert result["success"] is True
        assert result["eliminated_player_id"] == "usr_c"
        assert result["vote_count"]["usr_c"] == 2

    @pytest.mark.asyncio
    async def test_no_votes(self, game_service, mock_redis_client):
        """When nobody votes, no one is eliminated."""
        mock_redis_client.get_room_basic_data.return_value = {"current_round": "1"}
        mock_redis_client.hgetall.return_value = {}

        result = await game_service.tally_votes("ROOM1234")
        assert result["success"] is True
        assert result["eliminated_player_id"] is None
        assert result["reason"] == "no_votes"

    @pytest.mark.asyncio
    async def test_tied_votes_picks_one(self, game_service, mock_redis_client):
        """A tie should still produce an eliminated player (random choice)."""
        mock_redis_client.get_room_basic_data.return_value = {"current_round": "1"}
        mock_redis_client.hgetall.return_value = {
            "usr_a": "usr_b",
            "usr_b": "usr_a",
        }

        result = await game_service.tally_votes("ROOM1234")
        assert result["success"] is True
        assert result["eliminated_player_id"] in ("usr_a", "usr_b")
        assert len(result["tied_players"]) == 2

    @pytest.mark.asyncio
    async def test_time_suffix_keys_ignored(self, game_service, mock_redis_client):
        """Keys ending with _time are metadata and should not count as votes."""
        mock_redis_client.get_room_basic_data.return_value = {"current_round": "2"}
        mock_redis_client.hgetall.return_value = {
            "usr_a": "usr_b",
            "usr_a_time": "1.5",
        }

        result = await game_service.tally_votes("ROOM1234")
        assert result["vote_count"] == {"usr_b": 1}


# ---------------------------------------------------------------------------
# check_game_end_condition
# ---------------------------------------------------------------------------

class TestCheckGameEndCondition:

    @pytest.mark.asyncio
    async def test_civilians_win_when_all_spies_eliminated(self, game_service, mock_redis_client):
        mock_redis_client.hgetall.return_value = {
            "usr_a": ROLE_CIVILIAN,
            "usr_b": ROLE_CIVILIAN,
            "usr_c": ROLE_SPY,
        }
        mock_redis_client.zrange.return_value = ["usr_a", "usr_b"]

        result = await game_service.check_game_end_condition("ROOM1234")
        assert result["game_end"] is True
        assert result["winning_role"] == ROLE_CIVILIAN

    @pytest.mark.asyncio
    async def test_spies_win_when_equal_to_civilians(self, game_service, mock_redis_client):
        mock_redis_client.hgetall.return_value = {
            "usr_a": ROLE_CIVILIAN,
            "usr_b": ROLE_SPY,
        }
        mock_redis_client.zrange.return_value = ["usr_a", "usr_b"]

        result = await game_service.check_game_end_condition("ROOM1234")
        assert result["game_end"] is True
        assert result["winning_role"] == ROLE_SPY

    @pytest.mark.asyncio
    async def test_spies_win_when_outnumber_civilians(self, game_service, mock_redis_client):
        mock_redis_client.hgetall.return_value = {
            "usr_a": ROLE_CIVILIAN,
            "usr_b": ROLE_SPY,
            "usr_c": ROLE_SPY,
        }
        mock_redis_client.zrange.return_value = ["usr_a", "usr_b", "usr_c"]

        result = await game_service.check_game_end_condition("ROOM1234")
        assert result["game_end"] is True
        assert result["winning_role"] == ROLE_SPY

    @pytest.mark.asyncio
    async def test_game_continues_when_civilians_outnumber_spies(self, game_service, mock_redis_client):
        mock_redis_client.hgetall.return_value = {
            "usr_a": ROLE_CIVILIAN,
            "usr_b": ROLE_CIVILIAN,
            "usr_c": ROLE_SPY,
        }
        mock_redis_client.zrange.return_value = ["usr_a", "usr_b", "usr_c"]

        result = await game_service.check_game_end_condition("ROOM1234")
        assert result["game_end"] is False

    @pytest.mark.asyncio
    async def test_no_roles_returns_not_ended(self, game_service, mock_redis_client):
        mock_redis_client.hgetall.return_value = {}

        result = await game_service.check_game_end_condition("ROOM1234")
        assert result["game_end"] is False

    @pytest.mark.asyncio
    async def test_no_alive_players_returns_not_ended(self, game_service, mock_redis_client):
        mock_redis_client.hgetall.return_value = {"usr_a": ROLE_CIVILIAN}
        mock_redis_client.zrange.return_value = []

        result = await game_service.check_game_end_condition("ROOM1234")
        assert result["game_end"] is False

    @pytest.mark.asyncio
    async def test_god_role_not_counted(self, game_service, mock_redis_client):
        """God players should not affect the civilian/spy balance."""
        mock_redis_client.hgetall.return_value = {
            "usr_god": ROLE_GOD,
            "usr_a": ROLE_CIVILIAN,
            "usr_b": ROLE_CIVILIAN,
            "usr_c": ROLE_SPY,
        }
        # God is not in alive_players
        mock_redis_client.zrange.return_value = ["usr_a", "usr_b", "usr_c"]

        result = await game_service.check_game_end_condition("ROOM1234")
        assert result["game_end"] is False
