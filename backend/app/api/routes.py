from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.api.bid_policy_models import BidPolicyRequest, resolve_bid_policy, resolve_k_policy
from app.engine.k_policy import KPolicyMode
from app.engine.game_manager import game_manager

router = APIRouter()


class CreateGameRequest(BaseModel):
    startingBidderIndex: int = Field(ge=0, le=3)
    first4Hands: list[list[str]]
    biddingPolicy: BidPolicyRequest | None = None
    kPolicy: KPolicyMode | None = None
    botThinkTimeSeconds: float = Field(default=30.0, ge=1.0, le=120.0)


class CreateGameAutoRequest(BaseModel):
    startingBidderIndex: int = Field(ge=0, le=3)
    biddingPolicy: BidPolicyRequest | None = None
    kPolicy: KPolicyMode | None = None
    botThinkTimeSeconds: float = Field(default=30.0, ge=1.0, le=120.0)


class CreateGameResponse(BaseModel):
    gameId: str


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.post("/games/auto", response_model=CreateGameResponse)
def create_game_auto(req: CreateGameAutoRequest) -> CreateGameResponse:
    """Create a new game with automatic card dealing."""
    try:
        state = game_manager.create_game_auto_deal(
            starting_bidder_index=req.startingBidderIndex,
            bot_bidding_policy=resolve_bid_policy(req.biddingPolicy),
            bot_k_policy=resolve_k_policy(req.kPolicy),
            bot_think_timeout_seconds=req.botThinkTimeSeconds,
        )
        return CreateGameResponse(gameId=state.game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/games", response_model=CreateGameResponse)
def create_game(req: CreateGameRequest) -> CreateGameResponse:
    try:
        state = game_manager.create_game_manual_first4(
            starting_bidder_index=req.startingBidderIndex,
            first4_hands=req.first4Hands,
            bot_bidding_policy=resolve_bid_policy(req.biddingPolicy),
            bot_k_policy=resolve_k_policy(req.kPolicy),
            bot_think_timeout_seconds=req.botThinkTimeSeconds,
        )
        return CreateGameResponse(gameId=state.game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/self-play/games", response_model=CreateGameResponse)
def create_self_play_game() -> CreateGameResponse:
    try:
        state = game_manager.create_self_play_game()
        return CreateGameResponse(gameId=state.game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/games/{game_id}")
def get_game(game_id: str) -> dict:
    state = game_manager.get_game(game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game not found")
    return state.to_public_dict()
