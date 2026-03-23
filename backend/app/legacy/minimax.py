import copy
from app.legacy.cards import Cards
import random
import numpy as np
import pickle
import math
import time
import json
import os

try:
    import rl428_minimax_rust as _rl428_minimax_rust
    _RUST_MINIMAX_AVAILABLE = True
except Exception:
    _rl428_minimax_rust = None
    _RUST_MINIMAX_AVAILABLE = False

_MINIMAX_BACKEND_REQUESTED = (
    os.getenv("APP_MINIMAX_BACKEND")
    or os.getenv("RL428_MINIMAX_BACKEND", "auto")
).strip().lower()
if _MINIMAX_BACKEND_REQUESTED in ("python", "py"):
    _MINIMAX_BACKEND_ACTIVE = "python"
elif _MINIMAX_BACKEND_REQUESTED == "rust":
    _MINIMAX_BACKEND_ACTIVE = "rust" if _RUST_MINIMAX_AVAILABLE else "rust_unavailable"
else:
    _MINIMAX_BACKEND_ACTIVE = "rust" if _RUST_MINIMAX_AVAILABLE else "python"

#Checks if all the cards is from the suit specified
def allTrump(cards,suit):
        for card in cards:
            if card.suit != suit:
                 break
        else:
             return True
        return False


# Saves the four player card arrays to a file.
def save_player_cards(filename, p1, p2, p3, p4):
    players = {
        "player1Cards": p1,
        "player2Cards": p2,
        "player3Cards": p3,
        "player4Cards": p4
    }
    with open(filename, "wb") as f:
        pickle.dump(players, f)
    print(f"Player cards saved to {filename}.")

# Loads the four player card arrays from a file and returns them.
def load_player_cards(filename):
    with open(filename, "rb") as f:
        players = pickle.load(f)
    print(f"Player cards loaded from {filename}.")
    return players["player1Cards"], players["player2Cards"], players["player3Cards"], players["player4Cards"]

#Based on the  current suit and trumpsuit it checks the existing cards to find the cards that match the current suit and trumpcards in the players hands
def validCard(cards,currentSuit,trumpSuit):
         
         curSuitInd = []
         trumpSuitInd = []
         count = 0

         for card in cards:
              if card.suit == currentSuit:
                   curSuitInd.append(count)
              if card.suit == trumpSuit:
                   trumpSuitInd.append(count)
              count+=1

         return curSuitInd,trumpSuitInd


# Pretty obv -> Prints the players cards
def printCards(cards):
        for card in cards:
                print(card.identity())

#Returns which players chance it is by adding 1 to the length of the state, for example if the state list is length 0 then its Player 1's chance
def chance(s):
    return (len(s)+1)

def reset(currentSuit,s,trumpPlayed,trumpIndice,chose):
       currentSuit = ""
       s = []
       trumpPlayed = False
       trumpIndice = [0,0,0,0]
       chose = False
       return currentSuit,s,trumpPlayed,trumpIndice,chose

#Takes the state of the game and returns the points of the winning team, positive if team1 and negative if team2
def checkwin_extended(s,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit):
    currentCatch = s
    if len(s)==4:
            maxIndex = 0 # Used to determine which players chance is next
            if trumpPlayed: #If the trump card is played somewhere in the catch
                maxOrder = -1 # Finds which trump is the highest 
                count = 0 # count variable which accounts for index
                points = 0 #Accumulates points

                for card in currentCatch:
                    
                    points += card.points
                    if trumpIndice[count] == 1: # trumpIndice has the indices at which trump was played Eg. [0,1,0,0]
                        if card.order > maxOrder:
                            maxOrder = card.order 
                            maxIndex = count
                    count+=1

                maxIndex = (playerChance+maxIndex)%4 # Does initial player + maxIndex(how many places away from initial player) mod 4 to get the highest player
                # print("The catch is: ")
                # printCards(s)
                # print("\n")
                # print(f"Player {maxIndex+1} played the highest card, the catch goes to team {players[maxIndex]['team']} getting {points} points")
                if players[maxIndex]['team'] == 1:
                    return [maxIndex,points]
                else:
                    return [maxIndex,-1*points]
            else:
                # This part of the code explores the case where trump wasnt played
                maxOrder = -1 # Same as earlier
                count = 0
                points = 0

                #Easily understandable- it iterates through all cards to find highest card of the starting suit
                for card in currentCatch:
                    
                    points += card.points
                    if card.suit == currentSuit:
                        if card.order > maxOrder:
                            maxOrder = card.order
                            maxIndex = count
                    count+=1
                

                maxIndex = (playerChance+maxIndex)%4 #inital player + maxIndex(how many places away from initial player) mod 4 to get the highest player
                # print("The catch is: ")
                # printCards(s)
                # print("\n")
                # print(f"Player {maxIndex+1} played the highest card, the catch goes to team {players[maxIndex]['team']} getting {points} points")
                if players[maxIndex]['team'] == 1:
                    return [maxIndex,points]
                else:
                    return [maxIndex,-1*points]
    else:
        return [0,-100]

#Takes the state of the game and returns the points of the winning team, positive if team1 and negative if team2
def checkwin(s,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit):
    currentCatch = s
    if len(s)==4:
            maxIndex = 0 # Used to determine which players chance is next
            if trumpPlayed: #If the trump card is played somewhere in the catch
                maxOrder = -1 # Finds which trump is the highest 
                count = 0 # count variable which accounts for index
                points = 0 #Accumulates points

                for card in currentCatch:
                    
                    points += card.points
                    if trumpIndice[count] == 1: # trumpIndice has the indices at which trump was played Eg. [0,1,0,0]
                        if card.order > maxOrder:
                            maxOrder = card.order 
                            maxIndex = count
                    count+=1

                maxIndex = (playerChance+maxIndex)%4 # Does initial player + maxIndex(how many places away from initial player) mod 4 to get the highest player
                # print("The catch is: ")
                # printCards(s)
                # print("\n")
                # print(f"Player {maxIndex+1} played the highest card, the catch goes to team {players[maxIndex]['team']} getting {points} points")
                if players[maxIndex]['team'] == 1:
                    return points
                else:
                    return -1*points
            else:
                # This part of the code explores the case where trump wasnt played
                maxOrder = -1 # Same as earlier
                count = 0
                points = 0

                #Easily understandable- it iterates through all cards to find highest card of the starting suit
                for card in currentCatch:
                    
                    points += card.points
                    if card.suit == currentSuit:
                        if card.order > maxOrder:
                            maxOrder = card.order
                            maxIndex = count
                    count+=1
                

                maxIndex = (playerChance+maxIndex)%4 #inital player + maxIndex(how many places away from initial player) mod 4 to get the highest player
                # print("The catch is: ")
                # printCards(s)
                # print("\n")
                # print(f"Player {maxIndex+1} played the highest card, the catch goes to team {players[maxIndex]['team']} getting {points} points")
                if players[maxIndex]['team'] == 1:
                    return points
                else:
                    return -1*points
    else:
        return -100
    
# Verify with rules and add the condition that when its the last trick, and the trump player hasnt revealed his trump then the when its played it behaves like an active trump
def actions(s,players,trumpReveal,trumpSuit,currentSuit,chose,finalBid,playerTrump,trumpPlayed,trumpIndice,reveal=-1,playerChance=0):
    # Gets the updated player chance by using mod for reset
    playerChance=(playerChance+len(s))%4
    if players[playerChance]['isTrump'] and not trumpReveal and len(players[playerChance]['cards'])==0 and not chose:
          return [True]
    #First player in in the catchs' chance
    if  (chance(s)-1)==0:
        # Trump Call Player
        if players[playerChance]['isTrump']:
                        # if len(players[playerChance]['cards'])==0 and trumpReveal and playerTrump is not None:
                        #       players[playerChance]['cards'].append(playerTrump)
                        #If trump is already revealed or the player has all trumps, all cards are valid
                        if trumpReveal or allTrump(players[playerChance]['cards'],trumpSuit):
                            return (players[playerChance]['cards'])
                        #If trump is not revealed then non trump cards are valid
                        else:
                            validCards = []
                            for j in range(len(players[playerChance]['cards'])):
                                if not players[playerChance]['cards'][j].suit == trumpSuit:
                                    validCards.append(players[playerChance]['cards'][j])
                            
                            return validCards
        else:
                            #First player but non trump implies all cards are valid
                             return (players[playerChance]['cards'])
    
    #Non first chance player
    else:
                    #Gets the indices of the current suit cards and trump suit cards from the player
                    curSuitInd,trumpSuitInd = validCard(players[playerChance]['cards'],currentSuit,trumpSuit)
                    if len(curSuitInd)>0: #If the player has cards of the current suit, he should play among them
                            
                            validCards = [players[playerChance]['cards'][i] for i in curSuitInd] # Returning the currentsuit cards back in a list
                            return validCards
                            
                            # selectValidCard(players[playerChance]['cards'],init="1",ind=curSuitInd) 
                    
                    #If player doesnt have cards of the current suit      
                    else:
                        # If the player has the option to reveal trump or not and he hasnt chosen then the 2 options is provided as actions
                        if not trumpReveal and not chose: 
                            return [False,True]
                        
                        # In this case the player chose one of the options and its stored in trumpreveal
                        elif chose: 
                            
                            #If player chose to reveal trump
                            if trumpReveal:
                                    
                                    
                                    # print("The trump is ",self.playerTrump.identity())
                                    # trumpReveal = True

                                    #If the current player is the player who put the trump down
                                    if playerChance == (finalBid-1): 
                                         
                                        #  print("You have played your trump")
                                        # playerTrump = None
                                        # trumpPlayed = True
                                        # trumpIndice[len(s)] = 1
                                        # players[finalBid-1]['cards'].append(playerTrump)
                                        return [playerTrump]
                                        #  self.currentCatch.append(self.playerTrump)


                                        #  self.trumpIndice[i] = 1
                                        #  for j in self.players[self.playerChance]['cards']:
                                        #     print(j.identity())
                                        #     print("\n\n")
                                        #     self.printCards(self.currentCatch)
                                        #     print(f"{self.currentSuit}, {self.playerChance}")
                                    
                                    # If its a non trump calling player and he has trump
                                    elif len(trumpSuitInd)>0:            
                                        
                                        # players[finalBid-1]['cards'].append(playerTrump)
                                        # playerTrump = None
                                        # trumpPlayed = True
                                        # trumpIndice[len(s)] = 1
                                        validCards = [players[playerChance]['cards'][i] for i in trumpSuitInd] # Returning the trumpsuit cards back in a list
                                        return validCards                                        

                                    #Non trump calling player and he doesnt have trump cards
                                    else:
                                        
                                        # players[finalBid-1]['cards'].append(playerTrump)
                                        # playerTrump = None
                                        return players[playerChance]['cards']
                            #Player chose not to reveal trump
                            else:
                                        
                                        return players[playerChance]['cards']

                        else:
                                
                                #Last Case: The card played by minimax should affect the variables related to trumpPlayed and trumpIndice depending on whether the player played a trump card or not (It seems like its been taken care of in the result function)
                                return players[playerChance]['cards']
                        
# Removes a particular card from the set of cards
def removeCard(cards,card):
      for k in cards:
            if k.identity() == card.identity():
                cards.remove(k)
                break

#This function determines the change in state of the game when a particular action is taken
# Now returns undo information as well
def result(s,a,currentSuit,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,playerChance):
    # Track what we changed for undo
    undo_info = {
        'action_type': None,
        'prev_currentSuit': currentSuit,
        'prev_trumpReveal': trumpReveal,
        'prev_chose': chose,
        'prev_playerTrump': playerTrump,
        'prev_trumpPlayed': trumpPlayed,
        'prev_trumpIndice_state': None,  # Store (index, old_value)
        'card_removed_from_player': None,
        'card_removed': None,
        'card_removed_index': None,  # Store the index where card was removed
        'trump_added_to_player': None
    }
    
    # If action taken is card played
    if not (a == True or a == False): 
        undo_info['action_type'] = 'card'
        
        s.append(a)
        
        player_idx = (playerChance+len(s)-1)%4
        undo_info['card_removed_from_player'] = player_idx
        undo_info['card_removed'] = a
        
        # Store the index where the card was before removing it
        for idx, card in enumerate(players[player_idx]['cards']):
            card.identity()
            a.identity()
            if card.identity() == a.identity():
                undo_info['card_removed_index'] = idx
                break
        
        removeCard(players[player_idx]['cards'], a)
        
        # If its the first card played
        if len(s)==1: 
            currentSuit = a.suit
            
        #If its 2nd onward card played
        if trumpReveal and a.suit==trumpSuit:
            idx = len(s)-1
            undo_info['prev_trumpIndice_state'] = (idx, trumpIndice[idx])  # Store both index and old value
            trumpPlayed = True
            trumpIndice[idx] = 1

        if a==playerTrump:
            playerTrump = None

        chose = False

        return currentSuit,s,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,undo_info
    
    # If action taken is choosing or not choosing to reveal trump
    else: 
        undo_info['action_type'] = 'reveal_choice'
        
        if (a and ((playerChance+len(s))%4)!=finalBid-1): 
            players[finalBid-1]['cards'].append(playerTrump)
            undo_info['trump_added_to_player'] = finalBid-1
        elif a:
             players[finalBid-1]['cards'].append(playerTrump)
             undo_info['trump_added_to_player'] = finalBid-1

        chose = True
        trumpReveal = a
        return currentSuit,s,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,undo_info


# Undo function to reverse the changes made by result()
def undo_result(s, undo_info, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players):
    if undo_info['action_type'] == 'card':
        # Remove the card from state
        s.pop()
        
        # Add card back to player's hand at the original position
        if undo_info['card_removed_from_player'] is not None:
            players[undo_info['card_removed_from_player']]['cards'].insert(
                undo_info['card_removed_index'],
                undo_info['card_removed']
            )
        
        # Restore currentSuit
        currentSuit = undo_info['prev_currentSuit']
        
        # Restore trumpPlayed
        trumpPlayed = undo_info['prev_trumpPlayed']
        
        # Restore trumpIndice if it was modified
        if undo_info['prev_trumpIndice_state'] is not None:
            idx, prev_val = undo_info['prev_trumpIndice_state']
            trumpIndice[idx] = prev_val
        
        # Restore playerTrump
        playerTrump = undo_info['prev_playerTrump']
        
    elif undo_info['action_type'] == 'reveal_choice':
        # Remove trump card from player if it was added
        if undo_info['trump_added_to_player'] is not None:
            players[undo_info['trump_added_to_player']]['cards'].pop()
            playerTrump = undo_info['prev_playerTrump']
        
        # Restore chose and trumpReveal
        chose = undo_info['prev_chose']
        trumpReveal = undo_info['prev_trumpReveal']
    
    return currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice


# Helper function to capture state snapshot
def capture_state_snapshot(s, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players):
    """Captures a snapshot of the current state for validation"""
    snapshot = {
        's_len': len(s),
        's_cards': [card.identity() for card in s],
        'currentSuit': currentSuit,
        'trumpReveal': trumpReveal,
        'chose': chose,
        'playerTrump': playerTrump.identity() if playerTrump is not None else None,
        'trumpPlayed': trumpPlayed,
        'trumpIndice': trumpIndice[:],  # Copy the list
        'players_cards': []
    }
    
    # Capture each player's cards
    for i in range(4):
        snapshot['players_cards'].append([card.identity() for card in players[i]['cards']])
    
    return snapshot


# Helper function to validate state after undo
def validate_state_restoration(snapshot, s, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players):
    """Validates that the state matches the snapshot"""
    errors = []
    
    # Check s length
    if len(s) != snapshot['s_len']:
        errors.append(f"s length mismatch: expected {snapshot['s_len']}, got {len(s)}")
    
    # Check s cards
    s_cards_now = [card.identity() for card in s]
    if s_cards_now != snapshot['s_cards']:
        errors.append(f"s cards mismatch: expected {snapshot['s_cards']}, got {s_cards_now}")
    
    # Check currentSuit
    if currentSuit != snapshot['currentSuit']:
        errors.append(f"currentSuit mismatch: expected '{snapshot['currentSuit']}', got '{currentSuit}'")
    
    # Check trumpReveal
    if trumpReveal != snapshot['trumpReveal']:
        errors.append(f"trumpReveal mismatch: expected {snapshot['trumpReveal']}, got {trumpReveal}")
    
    # Check chose
    if chose != snapshot['chose']:
        errors.append(f"chose mismatch: expected {snapshot['chose']}, got {chose}")
    
    # Check playerTrump
    playerTrump_now = playerTrump.identity() if playerTrump is not None else None
    if playerTrump_now != snapshot['playerTrump']:
        errors.append(f"playerTrump mismatch: expected {snapshot['playerTrump']}, got {playerTrump_now}")
    
    # Check trumpPlayed
    if trumpPlayed != snapshot['trumpPlayed']:
        errors.append(f"trumpPlayed mismatch: expected {snapshot['trumpPlayed']}, got {trumpPlayed}")
    
    # Check trumpIndice
    if trumpIndice != snapshot['trumpIndice']:
        errors.append(f"trumpIndice mismatch: expected {snapshot['trumpIndice']}, got {trumpIndice}")
    
    # Check players' cards
    for i in range(4):
        cards_now = [card.identity() for card in players[i]['cards']]
        if cards_now != snapshot['players_cards'][i]:
            errors.append(f"Player {i} cards mismatch: expected {snapshot['players_cards'][i]}, got {cards_now}")
    
    return errors


def minimax(s,first,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution):
    # Only deepcopy on first call to preserve original state
    if first:
        s = copy.deepcopy(s)
        trumpIndice = copy.deepcopy(trumpIndice)
        players = copy.deepcopy(players)
      
    if checkwin(s,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit)!=-100:
        return checkwin(s,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit)
    
    if (playerChance+chance(s))%2!=0:
        value = -1000
        act = actions(s,players,trumpReveal,trumpSuit,currentSuit,chose,finalBid,playerTrump,trumpPlayed,trumpIndice,reveal,playerChance)
        
        # Save the original chose value before the loop
        # original_chose = chose
        chose = False
        
        for a in act:
            # VALIDATION: Capture state before applying action
            snapshot = capture_state_snapshot(s, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players)
            
            # Apply action and get undo info
            currentSuit,s,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,undo_info = result(s,a,currentSuit,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,playerChance)
            
            # Recurse
            newtake = minimax(s,False,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution)
            value = max(value,newtake)
            
            # Undo the action
            currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice = undo_result(s, undo_info, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players)
            
            # # VALIDATION: Check if state was restored correctly
            errors = validate_state_restoration(snapshot, s, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players)
            if errors:
                print("\n" + "="*80)
                print("UNDO VALIDATION FAILED!")
                print("="*80)
                for error in errors:
                    print(f"  ❌ {error}")
                print("="*80)
                raise AssertionError(f"Undo operation failed: {len(errors)} mismatches found")
            
            if first:
                reward_distribution.append(newtake)
        
        # Restore chose to its original value after the loop
        # chose = original_chose
                
    else:
        value = 1000
        act1 = actions(s,players,trumpReveal,trumpSuit,currentSuit,chose,finalBid,playerTrump,trumpPlayed,trumpIndice,reveal,playerChance) 
        
        # Save the original chose value before the loop
        # original_chose = chose
        chose = False
        
        for a in act1:
            # VALIDATION: Capture state before applying action
            snapshot = capture_state_snapshot(s, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players)
            
            # Apply action and get undo info
            currentSuit,s,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,undo_info = result(s,a,currentSuit,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,playerChance)
            
            # Recurse
            newtake = minimax(s,False,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution)
            value = min(value,newtake)
            
            # Undo the action
            currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice = undo_result(s, undo_info, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players)
            
            # # VALIDATION: Check if state was restored correctly
            errors = validate_state_restoration(snapshot, s, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players)
            if errors:
                print("\n" + "="*80)
                print("UNDO VALIDATION FAILED!")
                print("="*80)
                for error in errors:
                    print(f"  ❌ {error}")
                print("="*80)
                raise AssertionError(f"Undo operation failed: {len(errors)} mismatches found")

            if first:
                reward_distribution.append(newtake)
        
        # Restore chose to its original value after the loop
        # chose = original_chose
    
    return value



def minimax_alpha(s,first,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,alpha=-math.inf,beta=math.inf):
    if first:
        s = copy.deepcopy(s)
        trumpIndice = copy.deepcopy(trumpIndice)
        players = copy.deepcopy(players)
    
    chk = checkwin(s,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit)

    if chk!=-100:
        return chk
    
    if (playerChance+chance(s))%2!=0:
        value = -math.inf
        act = copy.deepcopy(actions(s,players,trumpReveal,trumpSuit,currentSuit,chose,finalBid,playerTrump,trumpPlayed,trumpIndice,reveal,playerChance))
        chose = False
        for a in act:
            s_copy = copy.deepcopy(s)
            currentSuit_copy = copy.deepcopy(currentSuit)
            trumpReveal_copy = copy.deepcopy(trumpReveal)
            chose_copy = copy.deepcopy(chose) 
            playerTrump_copy = copy.deepcopy(playerTrump)
            trumpPlayed_copy = copy.deepcopy(trumpPlayed)
            trumpIndice_copy = copy.deepcopy(trumpIndice)
            players_copy = copy.deepcopy(players)
            
            currentSuit,s,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid = result(s,a,currentSuit,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,playerChance)
            newtake = minimax_alpha(s,False,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,alpha,beta)
            value = max(value,newtake)
            alpha = max(alpha,value)
            
            s = s_copy
            currentSuit = currentSuit_copy
            trumpReveal = trumpReveal_copy
            chose = chose_copy
            playerTrump = playerTrump_copy
            trumpPlayed = trumpPlayed_copy
            trumpIndice = trumpIndice_copy
            players = players_copy
            
            if first and (len(reward_distribution)==0 or newtake>reward_distribution[0][1]):
                reward_distribution.clear()
                if isinstance(a, bool):
                     reward_distribution.append((a,newtake))
                else:
                     reward_distribution.append((a.identity(),newtake))

            if alpha>=beta:
                break
    else:
        value = math.inf
        act1 =  copy.deepcopy(actions(s,players,trumpReveal,trumpSuit,currentSuit,chose,finalBid,playerTrump,trumpPlayed,trumpIndice,reveal,playerChance)) 
        chose = False
        for a in act1:
            s_copy1 = copy.deepcopy(s)
            currentSuit_copy1 = copy.deepcopy(currentSuit)
            trumpReveal_copy1 = copy.deepcopy(trumpReveal)
            chose_copy1 = copy.deepcopy(chose)
            playerTrump_copy1 = copy.deepcopy(playerTrump)
            trumpPlayed_copy1 = copy.deepcopy(trumpPlayed)
            trumpIndice_copy1 = copy.deepcopy(trumpIndice)
            players_copy1 = copy.deepcopy(players)
            
            currentSuit,s,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid = result(s,a,currentSuit,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,playerChance)
            newtake = minimax_alpha(s,False,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,alpha,beta)
            value = min(value,newtake)
            beta = min(beta,value)


            s = s_copy1
            currentSuit = currentSuit_copy1
            trumpReveal = trumpReveal_copy1
            chose = chose_copy1
            playerTrump = playerTrump_copy1
            trumpPlayed = trumpPlayed_copy1
            trumpIndice = trumpIndice_copy1
            players = players_copy1

            
            if first and (len(reward_distribution)==0 or newtake<reward_distribution[0][1]):
                reward_distribution.clear()
                if isinstance(a, bool):
                     reward_distribution.append((a,newtake))
                else:
                     reward_distribution.append((a.identity(),newtake))

            if alpha>=beta:
                break
            
    return value

# leaf_count = [1]
def _minimax_extended_python(s,first,secondary,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,alpha=-math.inf,beta=math.inf):
    if secondary:
        s = copy.deepcopy(s)
        trumpIndice = copy.deepcopy(trumpIndice)
        players = copy.deepcopy(players)
    
    chk = checkwin_extended(s,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit)

    if chk[1]!=-100:
         total+=chk[1]
         num+=1
         currentSuit,s,trumpPlayed,trumpIndice,chose = reset(currentSuit,s,trumpPlayed,trumpIndice,chose)
         playerChance = chk[0]
         if num<k:
            return _minimax_extended_python(s,False,True,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,alpha,beta)
         else:
            # print(leaf_count[0])
            # leaf_count[0]+=1
            return total
    
    if (playerChance+chance(s))%2!=0:
        value = -math.inf
        act = actions(s,players,trumpReveal,trumpSuit,currentSuit,chose,finalBid,playerTrump,trumpPlayed,trumpIndice,reveal,playerChance)
        chose = False
        for a in act:
            # s_copy = copy.deepcopy(s)
            # currentSuit_copy = copy.deepcopy(currentSuit)
            # trumpReveal_copy = copy.deepcopy(trumpReveal)
            # chose_copy = copy.deepcopy(chose) 
            # playerTrump_copy = copy.deepcopy(playerTrump)
            # trumpPlayed_copy = copy.deepcopy(trumpPlayed)
            # trumpIndice_copy = copy.deepcopy(trumpIndice)
            # players_copy = copy.deepcopy(players)
            
            currentSuit,s,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,undo_info = result(s,a,currentSuit,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,playerChance)
            newtake = _minimax_extended_python(s,False,False,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,alpha,beta)
            value = max(value,newtake)
            alpha = max(alpha,value)
            currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice = undo_result(s, undo_info, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players)
            
            
            # s = s_copy
            # currentSuit = currentSuit_copy
            # trumpReveal = trumpReveal_copy
            # chose = chose_copy
            # playerTrump = playerTrump_copy
            # trumpPlayed = trumpPlayed_copy
            # trumpIndice = trumpIndice_copy
            # players = players_copy
            
            if first and (len(reward_distribution)==0 or newtake>=reward_distribution[0][1]):
                if len(reward_distribution)>0 and newtake>reward_distribution[0][1]:
                    reward_distribution.clear()
                if isinstance(a, bool):
                     reward_distribution.append((a,newtake))
                else:
                     reward_distribution.append((a.identity(),newtake))

            if alpha>beta:
                break
    else:
        value = math.inf
        act1 =  actions(s,players,trumpReveal,trumpSuit,currentSuit,chose,finalBid,playerTrump,trumpPlayed,trumpIndice,reveal,playerChance)
        chose = False
        for a in act1:
            # s_copy1 = copy.deepcopy(s)
            # currentSuit_copy1 = copy.deepcopy(currentSuit)
            # trumpReveal_copy1 = copy.deepcopy(trumpReveal)
            # chose_copy1 = copy.deepcopy(chose)
            # playerTrump_copy1 = copy.deepcopy(playerTrump)
            # trumpPlayed_copy1 = copy.deepcopy(trumpPlayed)
            # trumpIndice_copy1 = copy.deepcopy(trumpIndice)
            # players_copy1 = copy.deepcopy(players)
            
            currentSuit,s,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,undo_info = result(s,a,currentSuit,trumpReveal,chose,playerTrump,trumpPlayed,trumpIndice,players,trumpSuit,finalBid,playerChance)
            newtake = _minimax_extended_python(s,False,False,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,alpha,beta)
           
            value = min(value,newtake)
            beta = min(beta,value)
            
            currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice = undo_result(s, undo_info, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players)
            


            # s = s_copy1
            # currentSuit = currentSuit_copy1
            # trumpReveal = trumpReveal_copy1
            # chose = chose_copy1
            # playerTrump = playerTrump_copy1
            # trumpPlayed = trumpPlayed_copy1
            # trumpIndice = trumpIndice_copy1
            # players = players_copy1

            
            if first and (len(reward_distribution)==0 or newtake<=reward_distribution[0][1]):
                if len(reward_distribution)>0 and newtake<reward_distribution[0][1]:
                    reward_distribution.clear()
                if isinstance(a, bool):
                     reward_distribution.append((a,newtake))
                else:
                     reward_distribution.append((a.identity(),newtake))

            if alpha>beta:
                break
    return value


def _card_to_payload(card):
    if card is None:
        return None
    return {
        "suit": card.suit,
        "rank": card.rank,
        "points": card.points,
        "order": card.order,
        "identity": card.identity(),
    }


def _player_to_payload(player):
    return {
        "cards": [_card_to_payload(card) for card in player["cards"]],
        "isTrump": player["isTrump"],
        "team": player["team"],
    }


def minimax_extended(s,first,secondary,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,alpha=-math.inf,beta=math.inf):
    if _MINIMAX_BACKEND_REQUESTED in ("python", "py"):
        return _minimax_extended_python(s,first,secondary,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,alpha,beta)

    if _MINIMAX_BACKEND_REQUESTED == "rust" and not _RUST_MINIMAX_AVAILABLE:
        raise RuntimeError(
            "APP_MINIMAX_BACKEND=rust requested, but rl428_minimax_rust is not available"
        )

    if not _RUST_MINIMAX_AVAILABLE:
        return _minimax_extended_python(s,first,secondary,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,alpha,beta)

    try:
        payload = {
            "s": [_card_to_payload(card) for card in s],
            "first": bool(first),
            "secondary": bool(secondary),
            "trumpPlayed": bool(trumpPlayed),
            "trumpIndice": [int(x) for x in trumpIndice],
            "playerChance": int(playerChance),
            "players": [_player_to_payload(player) for player in players],
            "currentSuit": currentSuit,
            "trumpReveal": bool(trumpReveal),
            "trumpSuit": trumpSuit,
            "chose": bool(chose),
            "finalBid": int(finalBid),
            "playerTrump": _card_to_payload(playerTrump),
            "total": int(total),
            "num": int(num),
            "k": int(k),
            "alpha": None if not math.isfinite(alpha) else float(alpha),
            "beta": None if not math.isfinite(beta) else float(beta),
        }

        result_json = _rl428_minimax_rust.minimax_extended_core(
            json.dumps(payload, separators=(",", ":"))
        )
        parsed = json.loads(result_json)

        reward_distribution.clear()
        for entry in parsed.get("reward_distribution", []):
            if entry.get("kind") == "bool":
                reward_distribution.append((bool(entry.get("action")), int(entry.get("value", 0))))
            else:
                reward_distribution.append((entry.get("action"), int(entry.get("value", 0))))

        return int(parsed["value"])
    except Exception:
        return _minimax_extended_python(s,first,secondary,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,alpha,beta)


def minimax_extended_suboptimal(s, first, secondary, trumpPlayed, currentCatch, trumpIndice, 
                                 playerChance, players, currentSuit, trumpReveal, trumpSuit, 
                                 chose, finalBid, playerTrump, reveal, reward_distribution, 
                                 total, num, k, alpha=-math.inf, beta=math.inf):
    """
    Suboptimal version using deepcopy and resetting alpha-beta bounds.
    Issues:
    - Uses deepcopy on every node (expensive)
    - Resets alpha-beta bounds to -inf/inf on recursive calls (breaks pruning)
    - Deepcopies the actions list unnecessarily
    """
    if secondary:
        s = copy.deepcopy(s)
        trumpIndice = copy.deepcopy(trumpIndice)
        players = copy.deepcopy(players)
    
    chk = checkwin_extended(s, trumpPlayed, currentCatch, trumpIndice, playerChance, players, currentSuit)

    if chk[1] != -100:
        total += chk[1]
        num += 1
        currentSuit, s, trumpPlayed, trumpIndice, chose = reset(currentSuit, s, trumpPlayed, trumpIndice, chose)
        playerChance = chk[0]
        
        if num < k:
            # Issue: Resets alpha-beta bounds (loses pruning!)
            return minimax_extended_suboptimal(
                s, False, True, trumpPlayed, currentCatch, trumpIndice, playerChance, 
                players, currentSuit, trumpReveal, trumpSuit, chose, finalBid, 
                playerTrump, reveal, reward_distribution, total, num, k, 
                alpha, beta
            )
        else:
            return total
    
    if (playerChance + chance(s)) % 2 != 0:
        # Maximizing player
        value = -math.inf
        # Issue: Unnecessary deepcopy of actions list
        act = copy.deepcopy(actions(s, players, trumpReveal, trumpSuit, currentSuit, 
                                     chose, finalBid, playerTrump, trumpPlayed, 
                                     trumpIndice, reveal, playerChance))
        chose = False
        
        for a in act:
            # Issue: Deepcopy entire state before recursion (expensive!)
            s_copy = copy.deepcopy(s)
            currentSuit_copy = copy.deepcopy(currentSuit)
            trumpReveal_copy = copy.deepcopy(trumpReveal)
            chose_copy = copy.deepcopy(chose)
            playerTrump_copy = copy.deepcopy(playerTrump)
            trumpPlayed_copy = copy.deepcopy(trumpPlayed)
            trumpIndice_copy = copy.deepcopy(trumpIndice)
            players_copy = copy.deepcopy(players)
            
            currentSuit, s, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players, trumpSuit, finalBid,_ = result(
                s, a, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, 
                trumpIndice, players, trumpSuit, finalBid, playerChance
            )
            
            # Issue: Resets alpha-beta bounds (loses pruning!)
            newtake = minimax_extended_suboptimal(
                s, False, False, trumpPlayed, currentCatch, trumpIndice, playerChance, 
                players, currentSuit, trumpReveal, trumpSuit, chose, finalBid, 
                playerTrump, reveal, reward_distribution, total, num, k, 
                alpha, beta
            )
            
            value = max(value, newtake)
            alpha = max(alpha, value)
            
            # Restore state from deepcopies
            s = s_copy
            currentSuit = currentSuit_copy
            trumpReveal = trumpReveal_copy
            chose = chose_copy
            playerTrump = playerTrump_copy
            trumpPlayed = trumpPlayed_copy
            trumpIndice = trumpIndice_copy
            players = players_copy
            
            if first and (len(reward_distribution) == 0 or newtake > reward_distribution[0][1]):
                reward_distribution.clear()
                if isinstance(a, bool):
                    reward_distribution.append((a, newtake))
                else:
                    reward_distribution.append((a.identity(), newtake))

            if alpha >= beta:
                break
                
    else:
        # Minimizing player
        value = math.inf
        # Issue: Unnecessary deepcopy of actions list
        act1 = copy.deepcopy(actions(s, players, trumpReveal, trumpSuit, currentSuit, 
                                      chose, finalBid, playerTrump, trumpPlayed, 
                                      trumpIndice, reveal, playerChance))
        chose = False
        
        for a in act1:
            # Issue: Deepcopy entire state before recursion (expensive!)
            s_copy1 = copy.deepcopy(s)
            currentSuit_copy1 = copy.deepcopy(currentSuit)
            trumpReveal_copy1 = copy.deepcopy(trumpReveal)
            chose_copy1 = copy.deepcopy(chose)
            playerTrump_copy1 = copy.deepcopy(playerTrump)
            trumpPlayed_copy1 = copy.deepcopy(trumpPlayed)
            trumpIndice_copy1 = copy.deepcopy(trumpIndice)
            players_copy1 = copy.deepcopy(players)
            
            currentSuit, s, trumpReveal, chose, playerTrump, trumpPlayed, trumpIndice, players, trumpSuit, finalBid,_ = result(
                s, a, currentSuit, trumpReveal, chose, playerTrump, trumpPlayed, 
                trumpIndice, players, trumpSuit, finalBid, playerChance
            )
            
            # Issue: Resets alpha-beta bounds (loses pruning!)
            newtake = minimax_extended_suboptimal(
                s, False, False, trumpPlayed, currentCatch, trumpIndice, playerChance, 
                players, currentSuit, trumpReveal, trumpSuit, chose, finalBid, 
                playerTrump, reveal, reward_distribution, total, num, k, 
                alpha, beta
            )
            
            value = min(value, newtake)
            beta = min(beta, value)

            # Restore state from deepcopies
            s = s_copy1
            currentSuit = currentSuit_copy1
            trumpReveal = trumpReveal_copy1
            chose = chose_copy1
            playerTrump = playerTrump_copy1
            trumpPlayed = trumpPlayed_copy1
            trumpIndice = trumpIndice_copy1
            players = players_copy1
            
            if first and (len(reward_distribution) == 0 or newtake < reward_distribution[0][1]):
                reward_distribution.clear()
                if isinstance(a, bool):
                    reward_distribution.append((a, newtake))
                else:
                    reward_distribution.append((a.identity(), newtake))

            if alpha >= beta:
                break
    
    return value

def create_dictionary(p1,p2,p3,p4,finalBid,playerTrump):
        playerCards = [p1,p2,p3,p4]
        players = []
        for i in range(4):
                player = {'cards':copy.deepcopy(playerCards[i]),'isTrump':i==(finalBid-1),'team':1 if i % 2 == 0 else 2, 'trump':playerTrump if i==(finalBid-1) else None}
                players.append(player)
        return players
        
            


# loaded_player1Cards, loaded_player2Cards, loaded_player3Cards, loaded_player4Cards = get_game1()
# finalBid = 1
# playerTrump = loaded_player1Cards.pop(1)
# players = create_dictionary(loaded_player1Cards,loaded_player2Cards,loaded_player3Cards,loaded_player4Cards,finalBid,playerTrump)
# trumpReveal = False
# trumpSuit = playerTrump.suit
# currentSuit = ""
# chose = False
# trumpPlayed = False
# trumpIndice = [0,0,0,0]
# reveal = -1
# currentCatch = []
# playerChance = 0
# reward_distribution = []
# s = []
# total = 0
# num = 0
# k = 2
# print(time.time())
# minimax_extended(s,True,True,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal,reward_distribution,total,num,k,-math.inf,math.inf)
# print(time.time())

# cards = Cards.packOf28()    
# random.shuffle(cards)

# player1Cards = cards[0:8]
# player2Cards = cards[8:16]
# player3Cards = cards[16:24]
# player4Cards = cards[24:32]

# print("Player 1:")
# printCards(player1Cards)
# print("\n")
# printCards(player2Cards)
# print("\n")
# printCards(player3Cards)
# print("\n")
# printCards(player4Cards)

# # Save the player card arrays to a file
# save_player_cards(save_filename, player1Cards, player2Cards, player3Cards, player4Cards)




# Later on (or in another program run) you can load the player card arrays back:
# save_filename = r"C:\Users\ryuk7\Projects\RL428\data\player_cards.pkl"
# loaded_player1Cards, loaded_player2Cards, loaded_player3Cards, loaded_player4Cards = load_player_cards(save_filename)



# x = copy.deepcopy(loaded_player1Cards)
# x1 = copy.deepcopy(loaded_player2Cards)
# x2 = copy.deepcopy(loaded_player3Cards)
# x3 = copy.deepcopy(loaded_player4Cards)

# avg_rewards = np.array([0,0,0,0,0,0,0,0])
# remainingCards = loaded_player2Cards+loaded_player3Cards+loaded_player4Cards
# loaded_player1Cards.remove(loaded_player1Cards[1])
# loaded_player1Cards.remove(loaded_player1Cards[2])
# loaded_player1Cards.remove(loaded_player1Cards[3])
# loaded_player2Cards.remove(loaded_player2Cards[1])
# loaded_player2Cards.remove(loaded_player2Cards[0])
# loaded_player2Cards.remove(loaded_player2Cards[5])
# loaded_player3Cards.remove(loaded_player3Cards[4])
# loaded_player3Cards.remove(loaded_player3Cards[5])
# loaded_player3Cards.remove(loaded_player3Cards[0])
# loaded_player4Cards.remove(loaded_player4Cards[1])
# loaded_player4Cards.remove(loaded_player4Cards[4])
# loaded_player4Cards.remove(loaded_player4Cards[0])
# lset = copy.deepcopy(loaded_player1Cards)
# lset2 = copy.deepcopy(loaded_player2Cards)
# lset3 = copy.deepcopy(loaded_player3Cards)
# lset4 = copy.deepcopy(loaded_player4Cards)
# printCards(loaded_player2Cards)
# print("\n")
# printCards(loaded_player2Cards)
# print("\n")
# printCards(loaded_player3Cards)
# print("\n")
# printCards(loaded_player4Cards)
# remainingCards = loaded_player2Cards+loaded_player3Cards+loaded_player4Cards
# sample_size = 0
# ranks = ["Seven","Eight","Queen","King","Ten","Ace","Nine","Jack"]

# # Create cards for Player 1
# nloaded_player1Cards = [
#     Cards("Hearts", "Seven", 0, ranks.index("Seven")),
#     Cards("Clubs", "Queen", 0, ranks.index("Queen")),
#     Cards("Spades", "Queen", 0, ranks.index("Queen")),
#     Cards("Spades", "Jack", 3, ranks.index("Jack")),
#     Cards("Diamonds", "Ace", 1, ranks.index("Ace")),
#     Cards("Clubs", "Ace", 1, ranks.index("Ace"))
# ]

# # Create cards for Player 2
# nloaded_player2Cards = [
#     Cards("Spades", "Seven", 0, ranks.index("Seven")),
#     Cards("Spades", "Ace", 1, ranks.index("Ace")),
#     Cards("Spades", "Ten", 1, ranks.index("Ten")),
#     Cards("Clubs", "Ten", 1, ranks.index("Ten")),
#     Cards("Clubs", "Nine", 2, ranks.index("Nine")),
#     Cards("Clubs", "Jack", 3, ranks.index("Jack"))
# ]

# # Create cards for Player 3
# nloaded_player3Cards = [
#     Cards("Spades", "Eight", 0, ranks.index("Eight")),
#     Cards("Spades", "Nine", 2, ranks.index("Nine")),
#     Cards("Diamonds", "Nine", 2, ranks.index("Nine")),
#     Cards("Hearts", "Queen", 0, ranks.index("Queen")),
#     Cards("Spades", "King", 0, ranks.index("King")),
#     Cards("Diamonds", "Queen", 0, ranks.index("Queen"))
# ]

# # Create cards for Player 4
# nloaded_player4Cards = [
#     Cards("Clubs", "Eight", 0, ranks.index("Eight")),
#     Cards("Diamonds", "Ten", 1, ranks.index("Ten")),
#     Cards("Hearts", "King", 0, ranks.index("King")),
#     Cards("Clubs", "Seven", 0, ranks.index("Seven")),
#     Cards("Clubs", "King", 0, ranks.index("King")),
#     Cards("Hearts", "Ace", 1, ranks.index("Ace"))
# ]
# print("Player 1:")
# printCards(loaded_player1Cards)
# print("\nPlayer 2:")
# printCards(loaded_player2Cards)
# print("\nPlayer 3:")
# printCards(loaded_player3Cards)
# print("\nPlayer 4:")
# printCards(loaded_player4Cards)
# for j in range(sample_size):
#     print(j)
#     random.shuffle(remainingCards)
#     # print(len(remainingCards))
#     # loaded_player1Cards = copy.deepcopy(nloaded_player1Cards)
#     # loaded_player2Cards = copy.deepcopy(nloaded_player2Cards)
#     # loaded_player3Cards = copy.deepcopy(nloaded_player3Cards)
#     # loaded_player4Cards = copy.deepcopy(nloaded_player4Cards)
#     # loaded_player1Cards = copy.deepcopy(remainingCards[0:5])
#     loaded_player2Cards = copy.deepcopy(remainingCards[0:8])
#     loaded_player3Cards = copy.deepcopy(remainingCards[8:16])
#     loaded_player4Cards = copy.deepcopy(remainingCards[16:24])
#     # print("Player 1:")
#     # printCards(loaded_player1Cards)
#     # print("\nPlayer 2:")
#     # printCards(loaded_player2Cards)
#     # print("\nPlayer 3:")
#     # printCards(loaded_player3Cards)
#     # print("\nPlayer 4:")
#     # printCards(loaded_player4Cards)
#     # print("P1:")
#     # printCards(loaded_player1Cards)
#     # print("\n")
#     # print("P2:")
#     # print("\n")
#     # printCards(loaded_player2Cards)
#     # print("P3:")
#     # print("\n")
#     # printCards(loaded_player3Cards)
#     # print("P4:")
#     # print("\n")
#     # printCards(loaded_player4Cards)
#     # loaded_player1Cards = copy.deepcopy(x)
#     # loaded_player2Cards = copy.deepcopy(x1)
#     # loaded_player3Cards = copy.deepcopy(x2)
#     # loaded_player4Cards = copy.deepcopy(x3)

#     # print("\nLoaded Player 1 Cards:")
#     # printCards(loaded_player1Cards)
#     # print("\nLoaded Player 2 Cards:")
#     # printCards(loaded_player2Cards)
#     # print("\nLoaded Player 3 Cards:")
#     # printCards(loaded_player3Cards)
#     # print("\nLoaded Player 4 Cards:")
#     # printCards(loaded_player4Cards)

#     s = []
#     # s = [copy.deepcopy(x[3]),copy.deepcopy(x1[0]),copy.deepcopy(x2[6])]
#     finalBid = 3
#     rand_int = random.randint(0,len(loaded_player3Cards)-1)
#     # rand_int = 3
#     playerTrump = loaded_player3Cards[rand_int]
#     loaded_player3Cards.remove(playerTrump)
#     playerCards = [loaded_player1Cards,loaded_player2Cards,loaded_player3Cards,loaded_player4Cards]
#     players = []



    # for i in range(4):
    #                 player = {'cards':copy.deepcopy(playerCards[i]),'isTrump':i==(finalBid-1),'team':1 if i % 2 == 0 else 2, 'trump':playerTrump if i==(finalBid-1) else None}
    #                 players.append(player)

#     trumpReveal = False
#     trumpSuit = playerTrump.suit
#     # currentSuit = "Clubs"
#     currentSuit = ""
#     chose = False
#     trumpPlayed = False
#     trumpIndice = [0,0,0,0]
#     reveal = -1
#     currentCatch = []
#     playerChance = 0


#     reward_distribution = []
    # minimax(s,True,trumpPlayed,currentCatch,trumpIndice,playerChance,players,currentSuit,trumpReveal,trumpSuit,chose,finalBid,playerTrump,reveal)
#     # print(reward_distribution)
#     if j==0:
#         avg_rewards = np.array(reward_distribution)
#     else:
#         avg_rewards = np.array(reward_distribution)+avg_rewards



# print("Loaded Player 1 Cards:")
# printCards(x)
# print("\n\n")
# print("Loaded Player 2 Cards:")
# printCards(x1)
# print("\n\n")
# print("Loaded Player 3 Cards:")
# printCards(x2)
# print("\n\n")
# print("Loaded Player 4 Cards:")
# printCards(x3)
# print("\n\n")
# print("Reward Distribution: Values")

# printCards(x)
# print(avg_rewards/sample_size)


    
