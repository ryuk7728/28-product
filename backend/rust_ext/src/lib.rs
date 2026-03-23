use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::json;

#[derive(Clone, Debug, Deserialize, Serialize)]
struct Card {
    suit: String,
    rank: String,
    points: i32,
    order: i32,
    identity: String,
}

#[derive(Clone, Debug, Deserialize)]
struct PlayerInput {
    cards: Vec<Card>,
    #[serde(rename = "isTrump")]
    is_trump: bool,
    team: i32,
}

#[derive(Clone, Debug)]
struct PlayerState {
    cards: Vec<Card>,
    is_trump: bool,
    team: i32,
}

#[derive(Clone, Debug, Deserialize)]
struct SearchInput {
    s: Vec<Card>,
    first: bool,
    secondary: bool,
    #[serde(rename = "trumpPlayed")]
    trump_played: bool,
    #[serde(rename = "trumpIndice")]
    trump_indice: Vec<i32>,
    #[serde(rename = "playerChance")]
    player_chance: usize,
    players: Vec<PlayerInput>,
    #[serde(rename = "currentSuit")]
    current_suit: String,
    #[serde(rename = "trumpReveal")]
    trump_reveal: bool,
    #[serde(rename = "trumpSuit")]
    trump_suit: String,
    chose: bool,
    #[serde(rename = "finalBid")]
    final_bid: usize,
    #[serde(rename = "playerTrump")]
    player_trump: Option<Card>,
    total: i32,
    num: i32,
    k: i32,
    alpha: Option<f64>,
    beta: Option<f64>,
}

#[derive(Clone, Debug)]
struct GameState {
    s: Vec<Card>,
    trump_played: bool,
    trump_indice: Vec<i32>,
    player_chance: usize,
    players: Vec<PlayerState>,
    current_suit: String,
    trump_reveal: bool,
    trump_suit: String,
    chose: bool,
    final_bid: usize,
    player_trump: Option<Card>,
}

#[derive(Clone, Copy, Debug)]
enum Action {
    Card(usize),
    Reveal(bool),
}

#[derive(Clone, Debug)]
enum RewardAction {
    Bool(bool),
    Card(String),
}

#[derive(Clone, Debug)]
enum UndoActionType {
    Card,
    RevealChoice,
}

#[derive(Clone, Debug)]
struct UndoInfo {
    action_type: UndoActionType,
    prev_current_suit: String,
    prev_trump_reveal: bool,
    prev_chose: bool,
    prev_player_trump: Option<Card>,
    prev_trump_played: bool,
    prev_trump_indice_state: Option<(usize, i32)>,
    card_removed_from_player: Option<usize>,
    card_removed_index: Option<usize>,
    trump_added_to_player: Option<usize>,
}

#[derive(Serialize)]
struct RewardEntryOut {
    kind: String,
    action: serde_json::Value,
    value: i32,
}

#[derive(Serialize)]
struct SearchOutput {
    value: i32,
    reward_distribution: Vec<RewardEntryOut>,
}

fn chance(s_len: usize) -> usize {
    s_len + 1
}

fn all_trump(cards: &[Card], suit: &str) -> bool {
    cards.iter().all(|card| card.suit == suit)
}

fn valid_card(cards: &[Card], current_suit: &str, trump_suit: &str) -> (Vec<usize>, Vec<usize>) {
    let mut cur_suit_idx = Vec::new();
    let mut trump_suit_idx = Vec::new();

    for (idx, card) in cards.iter().enumerate() {
        if card.suit == current_suit {
            cur_suit_idx.push(idx);
        }
        if card.suit == trump_suit {
            trump_suit_idx.push(idx);
        }
    }

    (cur_suit_idx, trump_suit_idx)
}

fn action_label(state: &GameState, action: &Action) -> RewardAction {
    match action {
        Action::Reveal(v) => RewardAction::Bool(*v),
        Action::Card(idx) => {
            let player_idx = current_player(state);
            let identity = state
                .players
                .get(player_idx)
                .and_then(|p| p.cards.get(*idx))
                .map(|c| c.identity.clone())
                .unwrap_or_default();
            RewardAction::Card(identity)
        }
    }
}

fn current_player(state: &GameState) -> usize {
    (state.player_chance + state.s.len()) % 4
}

fn actions(state: &GameState) -> Vec<Action> {
    let player_idx = current_player(state);
    let player = &state.players[player_idx];

    let all_player_cards = || {
        player
            .cards
            .iter()
            .enumerate()
            .map(|(idx, _)| Action::Card(idx))
            .collect::<Vec<_>>()
    };

    if player.is_trump && !state.trump_reveal && player.cards.is_empty() && !state.chose {
        return vec![Action::Reveal(true)];
    }

    if chance(state.s.len()) - 1 == 0 {
        if player.is_trump {
            if state.trump_reveal || all_trump(&player.cards, &state.trump_suit) {
                return all_player_cards();
            }
            return player
                .cards
                .iter()
                .enumerate()
                .filter(|(_, card)| card.suit != state.trump_suit)
                .map(|(idx, _)| Action::Card(idx))
                .collect();
        }
        return all_player_cards();
    }

    let (cur_suit_idx, trump_suit_idx) =
        valid_card(&player.cards, &state.current_suit, &state.trump_suit);

    if !cur_suit_idx.is_empty() {
        return cur_suit_idx
            .iter()
            .map(|idx| Action::Card(*idx))
            .collect();
    }

    if !state.trump_reveal && !state.chose {
        return vec![Action::Reveal(false), Action::Reveal(true)];
    }

    if state.chose {
        if state.trump_reveal {
            if player_idx == state.final_bid.saturating_sub(1) {
                if let Some(card) = &state.player_trump {
                    if let Some(idx) = player.cards.iter().position(|c| c.identity == card.identity) {
                        return vec![Action::Card(idx)];
                    }
                    return Vec::new();
                }
                return Vec::new();
            }

            if !trump_suit_idx.is_empty() {
                return trump_suit_idx
                    .iter()
                    .map(|idx| Action::Card(*idx))
                    .collect();
            }
            return all_player_cards();
        }
        return all_player_cards();
    }

    all_player_cards()
}

fn remove_card_by_index(cards: &mut Vec<Card>, index: usize) -> Option<Card> {
    if index < cards.len() {
        return Some(cards.remove(index));
    }
    None
}

fn apply_result(state: &mut GameState, action: &Action) -> UndoInfo {
    let mut undo = UndoInfo {
        action_type: UndoActionType::Card,
        prev_current_suit: state.current_suit.clone(),
        prev_trump_reveal: state.trump_reveal,
        prev_chose: state.chose,
        prev_player_trump: state.player_trump.clone(),
        prev_trump_played: state.trump_played,
        prev_trump_indice_state: None,
        card_removed_from_player: None,
        card_removed_index: None,
        trump_added_to_player: None,
    };

    match action {
        Action::Card(index) => {
            undo.action_type = UndoActionType::Card;

            let player_idx = current_player(state);
            let removed_card = match remove_card_by_index(&mut state.players[player_idx].cards, *index) {
                Some(v) => v,
                None => return undo,
            };

            undo.card_removed_from_player = Some(player_idx);
            undo.card_removed_index = Some(*index);

            state.s.push(removed_card);
            let played_card = state.s.last().expect("card pushed into trick");

            if state.s.len() == 1 {
                state.current_suit = played_card.suit.clone();
            }

            if state.trump_reveal && played_card.suit == state.trump_suit {
                let idx = state.s.len() - 1;
                if idx >= state.trump_indice.len() {
                    state.trump_indice.resize(idx + 1, 0);
                }
                undo.prev_trump_indice_state = Some((idx, state.trump_indice[idx]));
                state.trump_played = true;
                state.trump_indice[idx] = 1;
            }

            if let Some(player_trump) = &state.player_trump {
                if player_trump.identity == played_card.identity {
                    state.player_trump = None;
                }
            }

            state.chose = false;
            undo
        }
        Action::Reveal(reveal_choice) => {
            undo.action_type = UndoActionType::RevealChoice;

            if *reveal_choice {
                if let Some(card) = &state.player_trump {
                    let bid_idx = state.final_bid.saturating_sub(1);
                    if bid_idx < state.players.len() {
                        state.players[bid_idx].cards.push(card.clone());
                        undo.trump_added_to_player = Some(bid_idx);
                    }
                }
            }

            state.chose = true;
            state.trump_reveal = *reveal_choice;
            undo
        }
    }
}

fn undo_result(state: &mut GameState, undo: UndoInfo) {
    match undo.action_type {
        UndoActionType::Card => {
            if let Some(card) = state.s.pop() {
                if let (Some(player_idx), Some(card_idx)) =
                    (undo.card_removed_from_player, undo.card_removed_index)
                {
                    if player_idx < state.players.len() {
                        let cards = &mut state.players[player_idx].cards;
                        if card_idx <= cards.len() {
                            cards.insert(card_idx, card);
                        } else {
                            cards.push(card);
                        }
                    }
                }
            }

            state.current_suit = undo.prev_current_suit;
            state.trump_played = undo.prev_trump_played;

            if let Some((idx, prev)) = undo.prev_trump_indice_state {
                if idx < state.trump_indice.len() {
                    state.trump_indice[idx] = prev;
                }
            }

            state.player_trump = undo.prev_player_trump;
        }
        UndoActionType::RevealChoice => {
            if let Some(player_idx) = undo.trump_added_to_player {
                if player_idx < state.players.len() && !state.players[player_idx].cards.is_empty() {
                    state.players[player_idx].cards.pop();
                }
            }
            state.player_trump = undo.prev_player_trump;
            state.chose = undo.prev_chose;
            state.trump_reveal = undo.prev_trump_reveal;
        }
    }
}

fn checkwin_extended(state: &GameState) -> Option<(usize, i32)> {
    if state.s.len() != 4 {
        return None;
    }

    let mut max_index = 0usize;
    let mut points = 0i32;

    if state.trump_played {
        let mut max_order = i32::MIN;
        for (idx, card) in state.s.iter().enumerate() {
            points += card.points;
            if idx < state.trump_indice.len() && state.trump_indice[idx] == 1 && card.order > max_order {
                max_order = card.order;
                max_index = idx;
            }
        }
    } else {
        let mut max_order = i32::MIN;
        for (idx, card) in state.s.iter().enumerate() {
            points += card.points;
            if card.suit == state.current_suit && card.order > max_order {
                max_order = card.order;
                max_index = idx;
            }
        }
    }

    let winner = (state.player_chance + max_index) % 4;
    let signed_points = if state.players[winner].team == 1 {
        points
    } else {
        -points
    };

    Some((winner, signed_points))
}

fn reset_state(state: &mut GameState) {
    state.current_suit.clear();
    state.s.clear();
    state.trump_played = false;
    state.trump_indice = vec![0, 0, 0, 0];
    state.chose = false;
}

fn update_root_rewards_max(
    first: bool,
    state: &GameState,
    action: &Action,
    score: i32,
    reward_distribution: &mut Vec<(RewardAction, i32)>,
) {
    if !first {
        return;
    }
    if reward_distribution.is_empty() || score >= reward_distribution[0].1 {
        if !reward_distribution.is_empty() && score > reward_distribution[0].1 {
            reward_distribution.clear();
        }
        reward_distribution.push((action_label(state, action), score));
    }
}

fn update_root_rewards_min(
    first: bool,
    state: &GameState,
    action: &Action,
    score: i32,
    reward_distribution: &mut Vec<(RewardAction, i32)>,
) {
    if !first {
        return;
    }
    if reward_distribution.is_empty() || score <= reward_distribution[0].1 {
        if !reward_distribution.is_empty() && score < reward_distribution[0].1 {
            reward_distribution.clear();
        }
        reward_distribution.push((action_label(state, action), score));
    }
}

fn minimax_extended_rec(
    state: &mut GameState,
    first: bool,
    total: i32,
    num: i32,
    k: i32,
    alpha: f64,
    beta: f64,
    reward_distribution: &mut Vec<(RewardAction, i32)>,
) -> i32 {
    if let Some((winner, signed_points)) = checkwin_extended(state) {
        let next_total = total + signed_points;
        let next_num = num + 1;
        let prev_player_chance = state.player_chance;
        let prev_current_suit = std::mem::take(&mut state.current_suit);
        let prev_s = std::mem::take(&mut state.s);
        let prev_trump_played = state.trump_played;
        let prev_trump_indice = std::mem::take(&mut state.trump_indice);
        let prev_chose = state.chose;

        reset_state(state);
        state.player_chance = winner;

        let outcome = if next_num < k {
            minimax_extended_rec(
                state,
                false,
                next_total,
                next_num,
                k,
                alpha,
                beta,
                reward_distribution,
            )
        } else {
            next_total
        };

        state.player_chance = prev_player_chance;
        state.current_suit = prev_current_suit;
        state.s = prev_s;
        state.trump_played = prev_trump_played;
        state.trump_indice = prev_trump_indice;
        state.chose = prev_chose;
        return outcome;
    }

    let maximizing = (state.player_chance + chance(state.s.len())) % 2 != 0;

    if maximizing {
        let mut value = i32::MIN;
        let mut local_alpha = alpha;
        let acts = actions(state);
        state.chose = false;

        for action in &acts {
            let undo = apply_result(state, action);
            let newtake = minimax_extended_rec(
                state,
                false,
                total,
                num,
                k,
                local_alpha,
                beta,
                reward_distribution,
            );
            value = value.max(newtake);
            local_alpha = local_alpha.max(value as f64);
            undo_result(state, undo);

            update_root_rewards_max(first, state, action, newtake, reward_distribution);

            if local_alpha > beta {
                break;
            }
        }

        value
    } else {
        let mut value = i32::MAX;
        let mut local_beta = beta;
        let acts = actions(state);
        state.chose = false;

        for action in &acts {
            let undo = apply_result(state, action);
            let newtake = minimax_extended_rec(
                state,
                false,
                total,
                num,
                k,
                alpha,
                local_beta,
                reward_distribution,
            );
            value = value.min(newtake);
            local_beta = local_beta.min(value as f64);
            undo_result(state, undo);

            update_root_rewards_min(first, state, action, newtake, reward_distribution);

            if alpha > local_beta {
                break;
            }
        }

        value
    }
}

fn reward_to_output(reward_distribution: Vec<(RewardAction, i32)>) -> Vec<RewardEntryOut> {
    reward_distribution
        .into_iter()
        .map(|(action, value)| match action {
            RewardAction::Bool(flag) => RewardEntryOut {
                kind: "bool".to_string(),
                action: json!(flag),
                value,
            },
            RewardAction::Card(identity) => RewardEntryOut {
                kind: "card".to_string(),
                action: json!(identity),
                value,
            },
        })
        .collect()
}

#[pyfunction]
fn minimax_extended_core(input_json: &str) -> PyResult<String> {
    let input: SearchInput =
        serde_json::from_str(input_json).map_err(|e| PyValueError::new_err(e.to_string()))?;

    let players = input
        .players
        .into_iter()
        .map(|player| PlayerState {
            cards: player.cards,
            is_trump: player.is_trump,
            team: player.team,
        })
        .collect::<Vec<_>>();

    let mut state = GameState {
        s: input.s,
        trump_played: input.trump_played,
        trump_indice: input.trump_indice,
        player_chance: input.player_chance,
        players,
        current_suit: input.current_suit,
        trump_reveal: input.trump_reveal,
        trump_suit: input.trump_suit,
        chose: input.chose,
        final_bid: input.final_bid,
        player_trump: input.player_trump,
    };

    if state.trump_indice.len() < 4 {
        state.trump_indice.resize(4, 0);
    }

    let mut reward_distribution: Vec<(RewardAction, i32)> = Vec::new();
    let alpha = input.alpha.unwrap_or(f64::NEG_INFINITY);
    let beta = input.beta.unwrap_or(f64::INFINITY);

    // `secondary` is parsed for API compatibility with Python calls.
    let _secondary = input.secondary;

    let value = minimax_extended_rec(
        &mut state,
        input.first,
        input.total,
        input.num,
        input.k,
        alpha,
        beta,
        &mut reward_distribution,
    );

    let output = SearchOutput {
        value,
        reward_distribution: reward_to_output(reward_distribution),
    };

    serde_json::to_string(&output).map_err(|e| PyValueError::new_err(e.to_string()))
}

#[pymodule]
fn rl428_minimax_rust(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(minimax_extended_core, m)?)?;
    Ok(())
}
