# Review of OPUS (SONNET)

Agree: SvGms excludes tiebreaks; identification identical (46,526 vs my 46,527 uniquely identified; naive set 1 0.613, sets 2+ 0.5016 identical); naive trap reproduced by null simulation; iid Markov gives exactly 0.500 for set 1; set 1 ~0.505-0.51.

1. Sets 2+ (0.444 mine vs 0.465 OPUS). Latent-order estimates for later sets are conditioning-sensitive. I re-ran my EM (review_check.py) binning by in-match serve-point gap instead of rank gap: set 1 0.496, sets 2+ 0.492, pooled 0.494 (bo3 sets 2+ 0.502). So 0.444..0.492 depending on control. Rank is a weak strength proxy (my simulation with *true* strength is already ~1pt low; weaker proxy -> more), so my 0.444 is biased low. The serve-rate version has the opposite problem (A is defined from outcome-correlated stats, so it absorbs the effect). OPUS's posterior (0.465) and its near-model-free B* (0.462) sit between and are the best-supported; the iid-Markov-with-selection null (0.451 sets 2+, 0.473 pooled) is the anchor. I withdraw 0.444/0.468.
2. Set 1: 0.506 vs 0.508 are consistent (CIs overlap; both ~0.5-1 pt above 0.500). My alt control gave 0.496, so the set-1 excess is within model uncertainty: sign-off 0.507 +/- 0.005.
3. Bo5 52.7%: not supported. Alt control gives 0.519 (bo5) vs 0.4915 (bo3), naive identified is 0.608 vs 0.614; no true bo5 effect is evident, so treat as model artefact (final sets/no-tiebreak rules, few identified matches). OPUS gives no bo5 set-1 figure; bo5 vs bo3 pooled differ little (0.477 vs 0.483).
4. Assumptions: mine - sets independent given rank bin (violated: momentum, in-match form). OPUS - in-match serve rates are outcome-dependent and the iid model ignores rebound; but its Brier/accuracy validation and B* agreement make it the safer. Neither found a coding bug.

Consensus: set 1 0.507 (0.50-0.51); sets 2+ 0.465 (+/-0.015, mostly selection, not a serve effect); pooled 0.481 (+/-0.01).
