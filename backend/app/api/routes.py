from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.engine.game_manager import game_manager

router = APIRouter()


class CreateGameRequest(BaseModel):
    startingBidderIndex: int = Field(ge=0, le=3)
    first4Hands: list[list[str]]


class CreateGameAutoRequest(BaseModel):
    startingBidderIndex: int = Field(ge=0, le=3)


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
        )
        return CreateGameResponse(gameId=state.game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/games/{game_id}")
def get_game(game_id: str) -> dict:
    state = game_manager.get_game(game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game not found")
    return state.to_public_dict()