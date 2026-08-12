from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.engine.room_manager import (
    RoomAssignment,
    RoomError,
    RoomFullError,
    RoomNotFoundError,
    RoomTokenError,
    room_manager,
)

router = APIRouter()


class CreateRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    playerName: str = Field(min_length=1, max_length=24)
    humanCount: int = Field(ge=1, le=4)
    startingBidderIndex: int | None = Field(default=None, ge=0, le=3)


class JoinRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roomCode: str
    playerToken: str | None = None
    playerName: str | None = Field(default=None, max_length=24)


class RoomJoinResponse(BaseModel):
    roomCode: str
    gameId: str | None
    seatIndex: int
    seatName: str
    playerToken: str
    waitingForPlayer: bool
    playersJoined: int
    targetHumanCount: int
    seats: list[dict[str, object]]


def _to_join_response(assignment: RoomAssignment) -> RoomJoinResponse:
    return RoomJoinResponse(
        roomCode=assignment.room_code,
        gameId=assignment.game_id,
        seatIndex=assignment.seat_index,
        seatName=assignment.seat_name,
        playerToken=assignment.player_token,
        waitingForPlayer=assignment.waiting_for_player,
        playersJoined=assignment.players_joined,
        targetHumanCount=assignment.target_human_count,
        seats=list(assignment.seats),
    )


@router.post("/rooms", response_model=RoomJoinResponse)
def create_room(req: CreateRoomRequest) -> RoomJoinResponse:
    try:
        return _to_join_response(
            room_manager.create_room(
                player_name=req.playerName,
                human_count=req.humanCount,
                starting_bidder_index=req.startingBidderIndex,
            )
        )
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rooms/join", response_model=RoomJoinResponse)
def join_room(req: JoinRoomRequest) -> RoomJoinResponse:
    try:
        return _to_join_response(
            room_manager.join_room(
                room_code=req.roomCode,
                player_token=req.playerToken,
                player_name=req.playerName,
            )
        )
    except RoomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RoomFullError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RoomTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RoomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/rooms/{room_code}")
def get_room_status(
    room_code: str, player_token: str | None = Query(default=None, alias="playerToken")
) -> dict[str, object]:
    try:
        return room_manager.get_room_status(
            room_code=room_code, player_token=player_token
        )
    except RoomNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
