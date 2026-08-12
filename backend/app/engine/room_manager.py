from __future__ import annotations

from dataclasses import dataclass, field
import secrets
import string
import threading
import time

from app.bots.bid_policy import BidPolicyConfig, BidThresholds
from app.engine.game_manager import game_manager
from app.engine.k_policy import KPolicyConfig
from app.settings import settings

ROOM_CODE_CHARS = string.ascii_uppercase + string.digits
ROOM_CODE_LENGTH = 6
PRODUCT_BOT_THINK_SECONDS = 30.0
PRODUCT_BID_POLICY = BidPolicyConfig.custom(
    BidThresholds(opening_15=60, opening_16=75, later_bid=60, jump_to_16=75),
    position_aware=False,
)
PRODUCT_K_POLICY = KPolicyConfig(mode="aggressive")
BOT_NAMES = ("Maya", "Arjun", "Zoya", "Kabir")


def initial_human_seats(human_count: int) -> tuple[int, ...]:
    """Product seating: two humans are partners; other modes read naturally."""
    plans = {
        1: (3,),
        2: (1, 3),
        3: (1, 2, 3),
        4: (0, 1, 2, 3),
    }
    try:
        return plans[human_count]
    except KeyError as exc:
        raise RoomError("humanCount must be between 1 and 4.") from exc


class RoomError(Exception):
    pass


class RoomNotFoundError(RoomError):
    pass


class RoomFullError(RoomError):
    pass


class RoomTokenError(RoomError):
    pass


@dataclass
class Room:
    code: str
    created_at: float
    starting_bidder_index: int
    target_human_count: int
    human_seats: tuple[int, ...]
    game_id: str | None = None
    seat_tokens: dict[int, str] = field(default_factory=dict)
    seat_names: dict[int, str] = field(default_factory=dict)
    rematch_ready_tokens: set[str] = field(default_factory=set)

    @property
    def players_joined(self) -> int:
        return len(self.seat_tokens)

    @property
    def waiting_for_player(self) -> bool:
        return self.players_joined < self.target_human_count

    @property
    def bot_seats(self) -> tuple[int, ...]:
        return tuple(seat for seat in range(4) if seat not in self.human_seats)


@dataclass(frozen=True)
class RoomAssignment:
    room_code: str
    seat_index: int
    player_token: str
    game_id: str | None
    seat_name: str
    waiting_for_player: bool
    players_joined: int
    target_human_count: int
    seats: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class RematchRequestResult:
    started: bool
    waiting_for_seats: tuple[int, ...]
    ready_seats: tuple[int, ...]
    starting_bidder_index: int | None


class RoomManager:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = threading.Lock()

    def _cleanup_expired_locked(self) -> None:
        now = time.time()
        ttl = max(60, settings.room_ttl_seconds)
        expired_codes: list[str] = []
        for code, room in self._rooms.items():
            if now - room.created_at <= ttl:
                continue
            expired_codes.append(code)
            if room.game_id:
                game_manager.delete_game(room.game_id)
        for code in expired_codes:
            self._rooms.pop(code, None)

    def _generate_code_locked(self) -> str:
        for _ in range(1000):
            code = "".join(secrets.choice(ROOM_CODE_CHARS) for _ in range(ROOM_CODE_LENGTH))
            if code not in self._rooms:
                return code
        raise RuntimeError("Unable to allocate unique room code")

    def _lookup_room_locked(self, room_code: str) -> Room:
        room = self._rooms.get(room_code.strip().upper())
        if room is None:
            raise RoomNotFoundError("That table does not exist or has expired.")
        return room

    @staticmethod
    def _find_seat_for_token_locked(room: Room, player_token: str) -> int | None:
        return next(
            (seat for seat, token in room.seat_tokens.items() if token == player_token),
            None,
        )

    @staticmethod
    def _normalize_player_name(player_name: str | None) -> str:
        cleaned = (player_name or "").strip()
        if not cleaned:
            raise RoomError("Enter your name to continue.")
        if len(cleaned) > 24:
            raise RoomError("Names can contain at most 24 characters.")
        return cleaned

    @staticmethod
    def _seat_roster_locked(room: Room) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "seatIndex": seat,
                "team": 1 if seat % 2 == 0 else 2,
                "type": "human" if seat in room.human_seats else "bot",
                "name": (
                    room.seat_names.get(seat, "Waiting...")
                    if seat in room.human_seats
                    else BOT_NAMES[seat]
                ),
                "joined": seat not in room.human_seats or seat in room.seat_tokens,
            }
            for seat in range(4)
        )

    def _apply_room_seats_to_state_locked(self, room: Room) -> None:
        if room.game_id is None:
            return
        state = game_manager.get_game(room.game_id)
        if state is None:
            return
        roster = self._seat_roster_locked(room)
        state.seat_types = [str(seat["type"]) for seat in roster]
        state.player_names = [str(seat["name"]) for seat in roster]

    def _ensure_game_created_locked(self, room: Room) -> None:
        if room.game_id is not None or room.waiting_for_player:
            return
        state = game_manager.create_game_auto_deal(
            starting_bidder_index=room.starting_bidder_index,
            bot_bidding_policy=PRODUCT_BID_POLICY,
            bot_k_policy=PRODUCT_K_POLICY,
            bot_think_timeout_seconds=PRODUCT_BOT_THINK_SECONDS,
        )
        room.game_id = state.game_id
        room.rematch_ready_tokens.clear()
        self._apply_room_seats_to_state_locked(room)

    def _assignment_locked(self, room: Room, seat: int, token: str) -> RoomAssignment:
        return RoomAssignment(
            room_code=room.code,
            seat_index=seat,
            player_token=token,
            game_id=room.game_id,
            seat_name=room.seat_names.get(seat, f"Player {seat + 1}"),
            waiting_for_player=room.waiting_for_player,
            players_joined=room.players_joined,
            target_human_count=room.target_human_count,
            seats=self._seat_roster_locked(room),
        )

    def create_room(
        self,
        *,
        player_name: str,
        human_count: int,
        starting_bidder_index: int | None = None,
    ) -> RoomAssignment:
        with self._lock:
            self._cleanup_expired_locked()
            human_seats = initial_human_seats(human_count)
            room = Room(
                code=self._generate_code_locked(),
                created_at=time.time(),
                starting_bidder_index=(
                    secrets.randbelow(4)
                    if starting_bidder_index is None
                    else starting_bidder_index
                ),
                target_human_count=human_count,
                human_seats=human_seats,
            )
            if not 0 <= room.starting_bidder_index <= 3:
                raise RoomError("startingBidderIndex must be between 0 and 3.")
            seat = human_seats[0]
            token = secrets.token_urlsafe(24)
            room.seat_tokens[seat] = token
            room.seat_names[seat] = self._normalize_player_name(player_name)
            self._rooms[room.code] = room
            self._ensure_game_created_locked(room)
            return self._assignment_locked(room, seat, token)

    def join_room(
        self,
        *,
        room_code: str,
        player_token: str | None = None,
        player_name: str | None = None,
    ) -> RoomAssignment:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)
            token = (player_token or "").strip()
            seat = self._find_seat_for_token_locked(room, token) if token else None

            if token and seat is None:
                raise RoomTokenError("This saved seat is no longer valid.")

            if seat is not None:
                if player_name:
                    room.seat_names[seat] = self._normalize_player_name(player_name)
                    self._apply_room_seats_to_state_locked(room)
                return self._assignment_locked(room, seat, token)

            if room.game_id is not None or not room.waiting_for_player:
                raise RoomFullError("This table is already full.")

            name = self._normalize_player_name(player_name)
            seat = next(
                (candidate for candidate in room.human_seats if candidate not in room.seat_tokens),
                None,
            )
            if seat is None:
                raise RoomFullError("This table is already full.")
            token = secrets.token_urlsafe(24)
            room.seat_tokens[seat] = token
            room.seat_names[seat] = name
            self._ensure_game_created_locked(room)
            return self._assignment_locked(room, seat, token)

    def get_room_status(
        self, *, room_code: str, player_token: str | None = None
    ) -> dict[str, object]:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)
            token = (player_token or "").strip()
            seat = self._find_seat_for_token_locked(room, token) if token else None
            return {
                "roomCode": room.code,
                "gameId": room.game_id,
                "seatIndex": seat,
                "seatName": room.seat_names.get(seat) if seat is not None else None,
                "waitingForPlayer": room.waiting_for_player,
                "playersJoined": room.players_joined,
                "targetHumanCount": room.target_human_count,
                "seats": list(self._seat_roster_locked(room)),
            }

    def validate_player(self, *, room_code: str, player_token: str) -> tuple[Room, int]:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)
            seat = self._find_seat_for_token_locked(room, player_token.strip())
            if seat is None:
                raise RoomTokenError("Invalid room token.")
            return room, seat

    def request_rematch(
        self, *, room_code: str, player_token: str
    ) -> RematchRequestResult:
        with self._lock:
            self._cleanup_expired_locked()
            room = self._lookup_room_locked(room_code)
            token = player_token.strip()
            seat = self._find_seat_for_token_locked(room, token)
            if seat is None:
                raise RoomTokenError("Invalid room token.")
            if room.game_id is None:
                raise RoomError("The game is not ready yet.")
            state = game_manager.get_game(room.game_id)
            if state is None or state.phase != "GAME_OVER":
                raise RoomError("Rematch is available only after the game ends.")

            room.rematch_ready_tokens.add(token)
            ready_seats = tuple(
                sorted(
                    seat_index
                    for seat_index, seat_token in room.seat_tokens.items()
                    if seat_token in room.rematch_ready_tokens
                )
            )
            if len(room.rematch_ready_tokens) < room.target_human_count:
                waiting = tuple(
                    sorted(
                        seat_index
                        for seat_index, seat_token in room.seat_tokens.items()
                        if seat_token not in room.rematch_ready_tokens
                    )
                )
                return RematchRequestResult(False, waiting, ready_seats, None)

            if room.target_human_count == 3:
                room.human_seats = tuple(sorted((seat_index + 1) % 4 for seat_index in room.human_seats))
                room.seat_tokens = {
                    (seat_index + 1) % 4: seat_token
                    for seat_index, seat_token in room.seat_tokens.items()
                }
                room.seat_names = {
                    (seat_index + 1) % 4: name
                    for seat_index, name in room.seat_names.items()
                }

            next_start = (state.starting_bidder_index + 1) % 4
            room.starting_bidder_index = next_start
            self._apply_room_seats_to_state_locked(room)
            game_manager.restart_game_in_place(state, starting_bidder_index=next_start)
            room.rematch_ready_tokens.clear()
            return RematchRequestResult(True, (), (), next_start)


room_manager = RoomManager()
