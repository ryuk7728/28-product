from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.bid_policy_models import BidPolicyRequest, resolve_bid_policy
from app.engine.room_manager import (
    RoomAssignment,
    RoomError,
    RoomFullError,
    RoomNotFoundError,
    room_manager,
)

router = APIRouter()


class CreateRoomRequest(BaseModel):
    startingBidderIndex: int | None = Field(default=None, ge=0, le=3)
    playerName: str = Field(min_length=1, max_length=24)
    biddingPolicy: BidPolicyRequest | None = None


class JoinRoomRequest(BaseModel):
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


def _to_join_response(assignment: RoomAssignment) -> RoomJoinResponse:
    return RoomJoinResponse(
        roomCode=assignment.room_code,
        gameId=assignment.game_id,
        seatIndex=assignment.seat_index,
        seatName=assignment.seat_name,
        playerToken=assignment.player_token,
        waitingForPlayer=assignment.waiting_for_player,
        playersJoined=assignment.players_joined,
    )


@router.post("/rooms", response_model=RoomJoinResponse)
def create_room(req: CreateRoomRequest) -> RoomJoinResponse:
    try:
        assignment = room_manager.create_room(
            player_name=req.playerName,
            starting_bidder_index=req.startingBidderIndex,
            bot_bidding_policy=resolve_bid_policy(req.biddingPolicy),
        )
        return _to_join_response(assignment)
    except RoomError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/rooms/join", response_model=RoomJoinResponse)
def join_room(req: JoinRoomRequest) -> RoomJoinResponse:
    try:
        assignment = room_manager.join_room(
            room_code=req.roomCode,
            player_token=req.playerToken,
            player_name=req.playerName,
        )
        return _to_join_response(assignment)
    except RoomNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RoomFullError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RoomError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/rooms/{room_code}")
def get_room_status(
    room_code: str, player_token: str | None = Query(default=None, alias="playerToken")
) -> dict[str, object]:
    try:
        return room_manager.get_room_status(
            room_code=room_code, player_token=player_token
        )
    except RoomNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
