import copy
import math
import os

from app.engine.cards_adapter import from_card_id
from app.legacy import minimax as legacy_minimax


def _cid(suit: str, rank: str) -> str:
    return f"{suit}_{rank}"


def _make_players():
    p1 = [
        _cid("Clubs", "Jack"),
        _cid("Clubs", "Ace"),
        _cid("Clubs", "Ten"),
        _cid("Spades", "Ten"),
        _cid("Spades", "Eight"),
        _cid("Spades", "Seven"),
        _cid("Diamonds", "Ace"),
        _cid("Diamonds", "Seven"),
    ]
    p2 = [
        _cid("Hearts", "Jack"),
        _cid("Hearts", "Nine"),
        _cid("Hearts", "King"),
        _cid("Spades", "Nine"),
        _cid("Spades", "King"),
        _cid("Diamonds", "Ten"),
        _cid("Diamonds", "Eight"),
        _cid("Hearts", "Eight"),
    ]
    p3 = [
        _cid("Diamonds", "Jack"),
        _cid("Diamonds", "King"),
        _cid("Diamonds", "Queen"),
        _cid("Hearts", "Ace"),
        _cid("Hearts", "Seven"),
        _cid("Clubs", "Nine"),
        _cid("Clubs", "King"),
        _cid("Clubs", "Queen"),
    ]
    p4 = [
        _cid("Spades", "Jack"),
        _cid("Spades", "Ace"),
        _cid("Spades", "Queen"),
        _cid("Clubs", "Eight"),
        _cid("Clubs", "Seven"),
        _cid("Diamonds", "Nine"),
        _cid("Hearts", "Ten"),
        _cid("Hearts", "Queen"),
    ]

    p1_cards = [from_card_id(x) for x in p1]
    p2_cards = [from_card_id(x) for x in p2]
    p3_cards = [from_card_id(x) for x in p3]
    p4_cards = [from_card_id(x) for x in p4]

    final_bid = 1
    player_trump = p1_cards.pop(0)
    players = legacy_minimax.create_dictionary(
        p1_cards, p2_cards, p3_cards, p4_cards, final_bid, player_trump
    )
    return players, player_trump, final_bid


def _run_case(
    *,
    s,
    trump_played,
    current_catch,
    trump_indice,
    player_chance,
    players,
    current_suit,
    trump_reveal,
    trump_suit,
    chose,
    final_bid,
    player_trump,
    reveal,
    total,
    num,
    k,
):
    reward_distribution = []
    legacy_minimax.minimax_extended(
        s=s,
        first=True,
        secondary=True,
        trumpPlayed=trump_played,
        currentCatch=current_catch,
        trumpIndice=trump_indice,
        playerChance=player_chance,
        players=players,
        currentSuit=current_suit,
        trumpReveal=trump_reveal,
        trumpSuit=trump_suit,
        chose=chose,
        finalBid=final_bid,
        playerTrump=player_trump,
        reveal=reveal,
        reward_distribution=reward_distribution,
        total=total,
        num=num,
        k=k,
        alpha=-math.inf,
        beta=math.inf,
    )
    for action, score in reward_distribution:
        print(f"{action} {float(score)}")


def main():
    players, player_trump, final_bid = _make_players()
    k = int(os.getenv("BENCH_K", "2"))

    base = {
        "s": [],
        "trump_played": False,
        "current_catch": [],
        "trump_indice": [0, 0, 0, 0],
        "player_chance": 0,
        "players": copy.deepcopy(players),
        "current_suit": "",
        "trump_reveal": False,
        "trump_suit": player_trump.suit,
        "chose": False,
        "final_bid": final_bid,
        "player_trump": player_trump,
        "reveal": -1,
        "total": 0,
        "num": 0,
        "k": k,
    }

    _run_case(**base)

    players2 = copy.deepcopy(players)
    current_suit2 = ""
    s2 = []
    trump_reveal2 = False
    chose2 = False
    player_trump2 = copy.deepcopy(player_trump)
    trump_played2 = False
    trump_indice2 = [0, 0, 0, 0]
    trump_suit2 = player_trump2.suit

    acts = legacy_minimax.actions(
        s2,
        players2,
        trump_reveal2,
        trump_suit2,
        current_suit2,
        chose2,
        final_bid,
        player_trump2,
        trump_played2,
        trump_indice2,
        -1,
        0,
    )
    first_action = acts[0]
    (
        current_suit2,
        s2,
        trump_reveal2,
        chose2,
        player_trump2,
        trump_played2,
        trump_indice2,
        players2,
        trump_suit2,
        final_bid2,
        _undo,
    ) = legacy_minimax.result(
        s2,
        first_action,
        current_suit2,
        trump_reveal2,
        chose2,
        player_trump2,
        trump_played2,
        trump_indice2,
        players2,
        trump_suit2,
        final_bid,
        0,
    )

    _run_case(
        s=s2,
        trump_played=trump_played2,
        current_catch=s2[:],
        trump_indice=trump_indice2,
        player_chance=0,
        players=players2,
        current_suit=current_suit2,
        trump_reveal=trump_reveal2,
        trump_suit=trump_suit2,
        chose=chose2,
        final_bid=final_bid2,
        player_trump=player_trump2,
        reveal=-1,
        total=0,
        num=0,
        k=k,
    )


if __name__ == "__main__":
    main()
