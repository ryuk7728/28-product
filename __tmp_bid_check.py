from app.engine.canonical_key import build_canonical_key_and_mapping as c 
from app.engine.rules_infer import predict_bid_and_trump_index as p 
hands=[['Spades_Nine','Clubs_Nine','Clubs_Eight','Spades_Jack'],['Spades_Nine','Spades_Jack','Clubs_Nine','Clubs_Jack'],['Spades_Nine','Clubs_Nine','Clubs_Jack','Spades_Jack']] 
for h in hands: 
    r=c(h) 
    bid,idx=p(r.canonical_groups) 
    print('HAND',h) 
    print('GROUPS',r.canonical_groups,'BID',bid,'TRUMP',r.flat_card_ids[idx]) 
    print('---') 
