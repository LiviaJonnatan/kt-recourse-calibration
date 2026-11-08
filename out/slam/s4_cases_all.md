# Case studies: three learners, history -> picks -> what happened


## Learner 1 (uid 1798), decision point at token 765 of 908

Last 8 exercises before the decision point (✓ correct, ✗ error):

- day 2.05 [lesson]: do✓ you✓ like✓ my✓ dish✓ the✓ salad✓ has✓ onions✓ i✓ eat✓ a✓ carrot✓
- day 2.06 [lesson]: the✓ cake✓ is✓ in✗ the✓ oven✓ the✓ cake✓ is✓ in✓ the✓ oven✓ more✓ pepper✓ please✓
- day 2.06 [lesson]: write✓ your✓ age✓ good✓ afternoon✓ in✓ the✓ afternoon✓ in✓ a✓ month✓
- day 3.24 [lesson]: in✓ april✓ it✓ is✓ january✓
- day 3.25 [lesson]: in✓ july✓ november✓ march✓ april✓ may✓ and✓ june✓ see✓ you✓ in✓ october✓
- day 3.25 [lesson]: i✓ like✓ the✓ fall✓ from✓ october✓ to✓ december✓ the✓ summer✗ is✓ a✓ season✓
- day 3.25 [lesson]: the✓ century✓ the✓ stage✓
- day 3.26 [lesson]: over✗ decades✓ good✓ night✓

About to do: exercise to6xQGKi (lesson), first token 'decades' (NOUN). Student-model P(correct) = 0.97. What actually happened over the next 5 NOUN tokens in later exercises: accuracy 1.00.

Candidate pool: 96 distinct recent tokens (7 corrections, 89 reviews).


**random** picked: 'sunday' (PROPN, review, seen ×2, last 2.2 d ago, τ_T=+0.017 τ_DR=+0.017, e=0.19, p_hlr=0.94); 'like' (VERB, review, seen ×7, last 9 min ago, τ_T=+0.032 τ_DR=+0.024, e=0.90, p_hlr=1.00); 'honey' (NOUN, review, seen ×1, last 1.2 d ago, τ_T=-0.006 τ_DR=+0.013, e=0.19, p_hlr=0.95); 'season' (NOUN, review, seen ×1, last 9 min ago, τ_T=+0.019 τ_DR=+0.016, e=0.43, p_hlr=1.00); 'from' (ADP, review, seen ×2, last 9 min ago, τ_T=+0.028 τ_DR=+0.016, e=0.98, p_hlr=1.00)

**stud_pcorrect** picked: 'next' (ADJ, review, seen ×2, last 2.2 d ago, τ_T=+0.040 τ_DR=+0.017, e=0.86, p_hlr=0.94); 'like' (VERB, review, seen ×7, last 9 min ago, τ_T=+0.032 τ_DR=+0.024, e=0.90, p_hlr=1.00); 'july' (PROPN, review, seen ×1, last 14 min ago, τ_T=+0.043 τ_DR=+0.019, e=0.18, p_hlr=1.00); 'more' (ADJ, review, seen ×3, last 1.2 d ago, τ_T=+0.029 τ_DR=+0.010, e=0.80, p_hlr=0.98); 'good' (ADJ, review, seen ×11, last 0 min ago, τ_T=+0.050 τ_DR=+0.015, e=0.95, p_hlr=1.00, REALIZED)

**ktcf_flip** picked: 'summer' (NOUN, correction, seen ×1, last 9 min ago, τ_T=+0.018 τ_DR=+0.004, e=0.63, p_hlr=1.00); 'over' (PROPN, correction, seen ×3, last 0 min ago, τ_T=+0.016 τ_DR=+0.014, e=0.18, p_hlr=1.00); 'body' (NOUN, correction, seen ×2, last 2.2 d ago, τ_T=-0.003 τ_DR=-0.007, e=0.43, p_hlr=0.93); 'against' (ADV, correction, seen ×2, last 1.7 d ago, τ_T=+0.023 τ_DR=+0.008, e=0.27, p_hlr=0.95); 'horse' (NOUN, correction, seen ×4, last 1.7 d ago, τ_T=-0.020 τ_DR=-0.002, e=0.92, p_hlr=0.97)

**hlr_lowest** picked: 'speak' (VERB, review, seen ×1, last 2.2 d ago, τ_T=+0.004 τ_DR=+0.015, e=0.12, p_hlr=0.90); 'which' (ADP, review, seen ×1, last 2.2 d ago, τ_T=+0.024 τ_DR=+0.018, e=0.11, p_hlr=0.90); 'who' (PRON, review, seen ×1, last 2.2 d ago, τ_T=+0.006 τ_DR=+0.020, e=0.16, p_hlr=0.90, REALIZED); 'fingers' (NOUN, review, seen ×1, last 2.2 d ago, τ_T=+0.021 τ_DR=+0.019, e=0.09, p_hlr=0.90); 'nose' (NOUN, review, seen ×1, last 2.2 d ago, τ_T=+0.010 τ_DR=+0.010, e=0.13, p_hlr=0.90)

**raw_gain** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.087 τ_DR=+0.057, e=0.98, p_hlr=1.00, REALIZED); 'do' (AUX, review, seen ×4, last 1.2 d ago, τ_T=+0.055 τ_DR=+0.028, e=0.14, p_hlr=0.98, REALIZED); 'my' (PRON, review, seen ×32, last 1.2 d ago, τ_T=+0.054 τ_DR=+0.029, e=0.99, p_hlr=1.00, REALIZED); 'good' (ADJ, review, seen ×11, last 0 min ago, τ_T=+0.050 τ_DR=+0.015, e=0.95, p_hlr=1.00, REALIZED); 'salad' (NOUN, review, seen ×2, last 1.2 d ago, τ_T=+0.049 τ_DR=+0.012, e=0.22, p_hlr=0.96)

**uplift_dr** picked: 'coffee' (NOUN, review, seen ×3, last 2.2 d ago, τ_T=+0.029 τ_DR=+0.071, e=0.91, p_hlr=0.96); 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.087 τ_DR=+0.057, e=0.98, p_hlr=1.00, REALIZED); 'black' (ADJ, review, seen ×2, last 2.2 d ago, τ_T=+0.032 τ_DR=+0.055, e=0.74, p_hlr=0.94); 'on' (ADP, review, seen ×2, last 2.2 d ago, τ_T=+0.017 τ_DR=+0.045, e=0.08, p_hlr=0.94); 'menu' (NOUN, review, seen ×3, last 1.7 d ago, τ_T=+0.012 τ_DR=+0.038, e=0.31, p_hlr=0.97)

**uplift_lcb** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.087 τ_DR=+0.057, e=0.98, p_hlr=1.00, REALIZED); 'my' (PRON, review, seen ×32, last 1.2 d ago, τ_T=+0.054 τ_DR=+0.029, e=0.99, p_hlr=1.00, REALIZED); 'write' (VERB, review, seen ×3, last 1.2 d ago, τ_T=+0.049 τ_DR=+0.014, e=0.11, p_hlr=0.98); 'dinner' (NOUN, review, seen ×6, last 1.7 d ago, τ_T=+0.044 τ_DR=+0.029, e=0.83, p_hlr=0.99); 'you' (PRON, review, seen ×8, last 14 min ago, τ_T=+0.045 τ_DR=+0.031, e=0.98, p_hlr=1.00, REALIZED)

**uplift_lcb_area** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.087 τ_DR=+0.057, e=0.98, p_hlr=1.00, REALIZED); 'my' (PRON, review, seen ×32, last 1.2 d ago, τ_T=+0.054 τ_DR=+0.029, e=0.99, p_hlr=1.00, REALIZED); 'write' (VERB, review, seen ×3, last 1.2 d ago, τ_T=+0.049 τ_DR=+0.014, e=0.11, p_hlr=0.98); 'dinner' (NOUN, review, seen ×6, last 1.7 d ago, τ_T=+0.044 τ_DR=+0.029, e=0.83, p_hlr=0.99); 'please' (INTJ, review, seen ×13, last 1.2 d ago, τ_T=+0.046 τ_DR=+0.027, e=0.99, p_hlr=1.00)

**uplift_full** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.087 τ_DR=+0.057, e=0.98, p_hlr=1.00, REALIZED); 'my' (PRON, review, seen ×32, last 1.2 d ago, τ_T=+0.054 τ_DR=+0.029, e=0.99, p_hlr=1.00, REALIZED); 'write' (VERB, review, seen ×3, last 1.2 d ago, τ_T=+0.049 τ_DR=+0.014, e=0.11, p_hlr=0.98); 'dinner' (NOUN, review, seen ×6, last 1.7 d ago, τ_T=+0.044 τ_DR=+0.029, e=0.83, p_hlr=0.99); 'please' (INTJ, review, seen ×13, last 1.2 d ago, τ_T=+0.046 τ_DR=+0.027, e=0.99, p_hlr=1.00)


## Learner 2 (uid 1414), decision point at token 967 of 1080

Last 8 exercises before the decision point (✓ correct, ✗ error):

- day 8.39 [lesson]: almost✗ almost✓ generally✓
- day 8.40 [lesson]: exactly✓ possibly✓
- day 8.40 [lesson]: nor✓ i✓ nor✓ i✓
- day 8.41 [lesson]: the✓ center✓ i✓ like✓ the✓ site✓ the✓ center✓
- day 8.41 [lesson]: the✓ coast✗ the✓ valley✓ the✓ station✓ the✓ ground✗ the✓ museum✓ the✓ zone✓
- day 8.42 [lesson]: the✓ port✓ the✓ right✓
- day 8.42 [lesson]: the✓ square✓ where✓ is✓ the✗ zoo✓ the✓ north✓ the✓ west✗
- day 8.42 [lesson]: where✓ is✓ my✓ book✓ easy✓

About to do: exercise Oe2PiaNC (lesson), first token 'come' (NOUN). Student-model P(correct) = 0.78. What actually happened over the next 5 NOUN tokens in later exercises: accuracy 0.80.

Candidate pool: 106 distinct recent tokens (10 corrections, 96 reviews).


**random** picked: 'interesting' (ADJ, review, seen ×1, last 1.3 h ago, τ_T=+0.040 τ_DR=-0.008, e=0.52, p_hlr=1.00); 'walk' (VERB, review, seen ×2, last 50 min ago, τ_T=+0.013 τ_DR=-0.007, e=0.37, p_hlr=1.00); 'you' (PRON, review, seen ×25, last 2.1 h ago, τ_T=+0.060 τ_DR=+0.035, e=0.65, p_hlr=1.00, REALIZED); 'a' (DET, review, seen ×28, last 50 min ago, τ_T=+0.088 τ_DR=+0.052, e=0.86, p_hlr=1.00, REALIZED); 'year' (NOUN, review, seen ×2, last 50 min ago, τ_T=+0.054 τ_DR=+0.019, e=0.69, p_hlr=1.00)

**stud_pcorrect** picked: 'where' (ADV, review, seen ×11, last 0 min ago, τ_T=+0.059 τ_DR=+0.029, e=0.84, p_hlr=1.00, REALIZED); 'never' (ADV, review, seen ×2, last 1.3 h ago, τ_T=+0.078 τ_DR=+0.028, e=0.53, p_hlr=1.00); 'name' (NOUN, review, seen ×4, last 2.2 h ago, τ_T=+0.051 τ_DR=+0.020, e=0.87, p_hlr=1.00); 'year' (NOUN, review, seen ×2, last 50 min ago, τ_T=+0.054 τ_DR=+0.019, e=0.69, p_hlr=1.00); 'she' (PRON, review, seen ×17, last 1.4 h ago, τ_T=+0.062 τ_DR=+0.043, e=0.90, p_hlr=1.00)

**ktcf_flip** picked: 'west' (ADJ, correction, seen ×1, last 7 min ago, τ_T=+0.012 τ_DR=+0.014, e=0.11, p_hlr=1.00); 'ground' (NOUN, correction, seen ×1, last 16 min ago, τ_T=+0.012 τ_DR=+0.012, e=0.42, p_hlr=1.00); 'are' (AUX, correction, seen ×18, last 2.1 h ago, τ_T=-0.043 τ_DR=+0.008, e=0.95, p_hlr=1.00, REALIZED); 'tuesday' (PROPN, correction, seen ×5, last 2.0 h ago, τ_T=+0.038 τ_DR=+0.017, e=0.30, p_hlr=1.00); 'and' (CONJ, correction, seen ×15, last 1.9 h ago, τ_T=+0.014 τ_DR=+0.049, e=0.91, p_hlr=1.00, REALIZED)

**hlr_lowest** picked: 'help' (INTJ, review, seen ×1, last 2.2 h ago, τ_T=+0.001 τ_DR=+0.018, e=0.46, p_hlr=1.00, REALIZED); 'live' (VERB, review, seen ×1, last 2.1 h ago, τ_T=+0.003 τ_DR=+0.005, e=0.21, p_hlr=1.00); 'spain' (PROPN, review, seen ×1, last 2.1 h ago, τ_T=+0.026 τ_DR=+0.003, e=0.24, p_hlr=1.00); 'old' (ADJ, review, seen ×1, last 2.1 h ago, τ_T=+0.046 τ_DR=+0.020, e=0.13, p_hlr=1.00); 'buying' (VERB, review, seen ×1, last 2.1 h ago, τ_T=+0.029 τ_DR=-0.006, e=0.71, p_hlr=1.00)

**raw_gain** picked: 'pretty' (ADV, review, seen ×1, last 1.3 h ago, τ_T=+0.097 τ_DR=-0.032, e=0.23, p_hlr=1.00); 'a' (DET, review, seen ×28, last 50 min ago, τ_T=+0.088 τ_DR=+0.052, e=0.86, p_hlr=1.00, REALIZED); 'never' (ADV, review, seen ×2, last 1.3 h ago, τ_T=+0.078 τ_DR=+0.028, e=0.53, p_hlr=1.00); 'she' (PRON, review, seen ×17, last 1.4 h ago, τ_T=+0.062 τ_DR=+0.043, e=0.90, p_hlr=1.00); 'you' (PRON, review, seen ×25, last 2.1 h ago, τ_T=+0.060 τ_DR=+0.035, e=0.65, p_hlr=1.00, REALIZED)

**uplift_dr** picked: 'a' (DET, review, seen ×28, last 50 min ago, τ_T=+0.088 τ_DR=+0.052, e=0.86, p_hlr=1.00, REALIZED); 'and' (CONJ, correction, seen ×15, last 1.9 h ago, τ_T=+0.014 τ_DR=+0.049, e=0.91, p_hlr=1.00, REALIZED); 'she' (PRON, review, seen ×17, last 1.4 h ago, τ_T=+0.062 τ_DR=+0.043, e=0.90, p_hlr=1.00); 'you' (PRON, review, seen ×25, last 2.1 h ago, τ_T=+0.060 τ_DR=+0.035, e=0.65, p_hlr=1.00, REALIZED); 'tomorrow' (NOUN, review, seen ×7, last 1.6 h ago, τ_T=+0.025 τ_DR=+0.030, e=0.89, p_hlr=1.00)

**uplift_lcb** picked: 'pretty' (ADV, review, seen ×1, last 1.3 h ago, τ_T=+0.097 τ_DR=-0.032, e=0.23, p_hlr=1.00); 'a' (DET, review, seen ×28, last 50 min ago, τ_T=+0.088 τ_DR=+0.052, e=0.86, p_hlr=1.00, REALIZED); 'you' (PRON, review, seen ×25, last 2.1 h ago, τ_T=+0.060 τ_DR=+0.035, e=0.65, p_hlr=1.00, REALIZED); 'she' (PRON, review, seen ×17, last 1.4 h ago, τ_T=+0.062 τ_DR=+0.043, e=0.90, p_hlr=1.00); 'me' (INTJ, review, seen ×8, last 1.3 h ago, τ_T=+0.058 τ_DR=+0.030, e=0.17, p_hlr=1.00)

**uplift_lcb_area** picked: 'pretty' (ADV, review, seen ×1, last 1.3 h ago, τ_T=+0.097 τ_DR=-0.032, e=0.23, p_hlr=1.00); 'a' (DET, review, seen ×28, last 50 min ago, τ_T=+0.088 τ_DR=+0.052, e=0.86, p_hlr=1.00, REALIZED); 'you' (PRON, review, seen ×25, last 2.1 h ago, τ_T=+0.060 τ_DR=+0.035, e=0.65, p_hlr=1.00, REALIZED); 'me' (INTJ, review, seen ×8, last 1.3 h ago, τ_T=+0.058 τ_DR=+0.030, e=0.17, p_hlr=1.00); 'passport' (NOUN, review, seen ×5, last 2.2 h ago, τ_T=+0.052 τ_DR=-0.003, e=0.43, p_hlr=1.00)

**uplift_full** picked: 'pretty' (ADV, review, seen ×1, last 1.3 h ago, τ_T=+0.097 τ_DR=-0.032, e=0.23, p_hlr=1.00); 'a' (DET, review, seen ×28, last 50 min ago, τ_T=+0.088 τ_DR=+0.052, e=0.86, p_hlr=1.00, REALIZED); 'you' (PRON, review, seen ×25, last 2.1 h ago, τ_T=+0.060 τ_DR=+0.035, e=0.65, p_hlr=1.00, REALIZED); 'me' (INTJ, review, seen ×8, last 1.3 h ago, τ_T=+0.058 τ_DR=+0.030, e=0.17, p_hlr=1.00); 'passport' (NOUN, review, seen ×5, last 2.2 h ago, τ_T=+0.052 τ_DR=-0.003, e=0.43, p_hlr=1.00)


## Learner 3 (uid 847), decision point at token 806 of 1050

Last 8 exercises before the decision point (✓ correct, ✗ error):

- day 18.74 [lesson]: again✓ please✓ go✓ away✓ try✗ again✓ again✓
- day 18.75 [lesson]: a✓ week✓ later✓ i✓ usually✓ walk✓ enough✓ a✓ year✓ later✓
- day 18.75 [lesson]: almost✗ almost✓ generally✓
- day 18.76 [lesson]: exactly✓ possibly✓ exactly✗
- day 18.76 [lesson]: nor✓ i✗ definitely✓ nor✓ i✓ eat✓ slowly✓
- day 19.71 [lesson]: i✓ am✓ in✗ the✓ city✓
- day 19.71 [lesson]: the✓ center✓ i✓ like✓ the✓ site✗ the✓ center✓
- day 22.71 [lesson]: the✓ valley✓ the✓

About to do: exercise rLeselu3 (lesson), first token 'ground' (NOUN). Student-model P(correct) = 0.92. What actually happened over the next 5 NOUN tokens in later exercises: accuracy 0.80.

Candidate pool: 96 distinct recent tokens (24 corrections, 72 reviews).


**random** picked: 'salt' (NOUN, correction, seen ×1, last 6.0 d ago, τ_T=-0.013 τ_DR=-0.005, e=0.53, p_hlr=0.73); 'only' (ADV, review, seen ×1, last 4.0 d ago, τ_T=+0.032 τ_DR=+0.019, e=0.10, p_hlr=0.83); 'nor' (PROPN, review, seen ×2, last 3.9 d ago, τ_T=+0.023 τ_DR=+0.126, e=0.43, p_hlr=0.89); 'valley' (NOUN, review, seen ×1, last 0 min ago, τ_T=-0.030 τ_DR=-0.002, e=0.10, p_hlr=1.00); 'my' (PRON, review, seen ×31, last 5.0 d ago, τ_T=+0.049 τ_DR=+0.028, e=0.99, p_hlr=1.00, REALIZED)

**stud_pcorrect** picked: 'she' (PRON, review, seen ×15, last 5.0 d ago, τ_T=+0.060 τ_DR=+0.045, e=0.99, p_hlr=0.99); 'year' (NOUN, review, seen ×2, last 4.0 d ago, τ_T=+0.027 τ_DR=+0.016, e=0.41, p_hlr=0.89); 'week' (NOUN, review, seen ×2, last 4.0 d ago, τ_T=+0.018 τ_DR=+0.011, e=0.60, p_hlr=0.89); 'they' (PRON, review, seen ×9, last 4.0 d ago, τ_T=+0.022 τ_DR=+0.015, e=0.85, p_hlr=0.98); 'he' (PRON, review, seen ×16, last 4.9 d ago, τ_T=+0.022 τ_DR=+0.026, e=0.90, p_hlr=1.00)

**ktcf_flip** picked: 'site' (NOUN, correction, seen ×1, last 3.0 d ago, τ_T=-0.010 τ_DR=+0.002, e=0.33, p_hlr=0.86); 'in' (ADP, correction, seen ×6, last 3.0 d ago, τ_T=-0.031 τ_DR=-0.001, e=0.96, p_hlr=0.98); 'salt' (NOUN, correction, seen ×1, last 6.0 d ago, τ_T=-0.013 τ_DR=-0.005, e=0.53, p_hlr=0.73); 'legal' (ADJ, correction, seen ×1, last 5.9 d ago, τ_T=+0.076 τ_DR=+0.010, e=0.20, p_hlr=0.73); 'clean' (ADJ, correction, seen ×1, last 5.9 d ago, τ_T=+0.077 τ_DR=-0.006, e=0.87, p_hlr=0.73)

**hlr_lowest** picked: 'salt' (NOUN, correction, seen ×1, last 6.0 d ago, τ_T=-0.013 τ_DR=-0.005, e=0.53, p_hlr=0.73); 'legal' (ADJ, correction, seen ×1, last 5.9 d ago, τ_T=+0.076 τ_DR=+0.010, e=0.20, p_hlr=0.73); 'clean' (ADJ, correction, seen ×1, last 5.9 d ago, τ_T=+0.077 τ_DR=-0.006, e=0.87, p_hlr=0.73); 'trust' (VERB, review, seen ×1, last 5.9 d ago, τ_T=+0.027 τ_DR=+0.015, e=0.45, p_hlr=0.76); 'different' (ADJ, review, seen ×1, last 5.9 d ago, τ_T=+0.096 τ_DR=+0.150, e=0.52, p_hlr=0.76)

**raw_gain** picked: 'dirty' (ADJ, review, seen ×1, last 5.9 d ago, τ_T=+0.156 τ_DR=-0.011, e=0.28, p_hlr=0.76); 'human' (ADJ, review, seen ×1, last 5.9 d ago, τ_T=+0.124 τ_DR=+0.057, e=0.67, p_hlr=0.76); 'future' (ADJ, review, seen ×1, last 5.0 d ago, τ_T=+0.114 τ_DR=+0.026, e=0.15, p_hlr=0.80); 'beautiful' (ADJ, review, seen ×1, last 5.0 d ago, τ_T=+0.106 τ_DR=-0.011, e=0.58, p_hlr=0.80); 'pretty' (ADV, review, seen ×1, last 4.9 d ago, τ_T=+0.102 τ_DR=+0.042, e=0.27, p_hlr=0.80)

**uplift_dr** picked: 'professional' (ADJ, review, seen ×4, last 5.0 d ago, τ_T=+0.034 τ_DR=+0.488, e=0.03, p_hlr=0.92); 'different' (ADJ, review, seen ×1, last 5.9 d ago, τ_T=+0.096 τ_DR=+0.150, e=0.52, p_hlr=0.76); 'away' (ADV, review, seen ×1, last 4.0 d ago, τ_T=-0.006 τ_DR=+0.150, e=0.10, p_hlr=0.83); 'nor' (PROPN, review, seen ×2, last 3.9 d ago, τ_T=+0.023 τ_DR=+0.126, e=0.43, p_hlr=0.89); 'religious' (ADJ, review, seen ×1, last 5.0 d ago, τ_T=+0.053 τ_DR=+0.086, e=0.52, p_hlr=0.80)

**uplift_lcb** picked: 'dirty' (ADJ, review, seen ×1, last 5.9 d ago, τ_T=+0.156 τ_DR=-0.011, e=0.28, p_hlr=0.76); 'human' (ADJ, review, seen ×1, last 5.9 d ago, τ_T=+0.124 τ_DR=+0.057, e=0.67, p_hlr=0.76); 'future' (ADJ, review, seen ×1, last 5.0 d ago, τ_T=+0.114 τ_DR=+0.026, e=0.15, p_hlr=0.80); 'beautiful' (ADJ, review, seen ×1, last 5.0 d ago, τ_T=+0.106 τ_DR=-0.011, e=0.58, p_hlr=0.80); 'pretty' (ADV, review, seen ×1, last 4.9 d ago, τ_T=+0.102 τ_DR=+0.042, e=0.27, p_hlr=0.80)

**uplift_lcb_area** picked: 'dirty' (ADJ, review, seen ×1, last 5.9 d ago, τ_T=+0.156 τ_DR=-0.011, e=0.28, p_hlr=0.76); 'pretty' (ADV, review, seen ×1, last 4.9 d ago, τ_T=+0.102 τ_DR=+0.042, e=0.27, p_hlr=0.80); 'a' (DET, review, seen ×21, last 4.0 d ago, τ_T=+0.073 τ_DR=+0.057, e=0.87, p_hlr=1.00, REALIZED); 'she' (PRON, review, seen ×15, last 5.0 d ago, τ_T=+0.060 τ_DR=+0.045, e=0.99, p_hlr=0.99); 'hello' (INTJ, review, seen ×6, last 5.0 d ago, τ_T=+0.066 τ_DR=+0.031, e=0.83, p_hlr=0.96)

**uplift_full** picked: 'dirty' (ADJ, review, seen ×1, last 5.9 d ago, τ_T=+0.156 τ_DR=-0.011, e=0.28, p_hlr=0.76); 'pretty' (ADV, review, seen ×1, last 4.9 d ago, τ_T=+0.102 τ_DR=+0.042, e=0.27, p_hlr=0.80); 'a' (DET, review, seen ×21, last 4.0 d ago, τ_T=+0.073 τ_DR=+0.057, e=0.87, p_hlr=1.00, REALIZED); 'she' (PRON, review, seen ×15, last 5.0 d ago, τ_T=+0.060 τ_DR=+0.045, e=0.99, p_hlr=0.99); 'hello' (INTJ, review, seen ×6, last 5.0 d ago, τ_T=+0.066 τ_DR=+0.031, e=0.83, p_hlr=0.96)


## Learner 4 (uid 2524), decision point at token 965 of 1186

Last 8 exercises before the decision point (✓ correct, ✗ error):

- day 14.00 [practice]: i✓ am✓ in✓ the✓ restaurant✓ monday✓ and✓ tuesday✓
- day 14.00 [practice]: i✓ have✓ a✓ turtle✗
- day 14.00 [practice]: he✓ plays✓ yes✓ he✓ plays✓
- day 14.00 [practice]: he✓ eats✓ fruit✓ i✓ eat✓ pork✓
- day 14.01 [practice]: why✓ me✓
- day 14.01 [practice]: the✓ moment✓ is✓ historical✗ the✓ answer✓ is✓ historical✗
- day 14.01 [practice]: i✓ like✓ turkey✓
- day 14.48 [practice]: a✓ good✓ weekend✓ i✓ like✓ the✗ weekend✓

About to do: exercise YYiB6F+f (practice), first token 'i' (PRON). Student-model P(correct) = 0.96. What actually happened over the next 5 PRON tokens in later exercises: accuracy 0.80.

Candidate pool: 93 distinct recent tokens (15 corrections, 78 reviews).


**random** picked: 'buying' (VERB, review, seen ×3, last 1.4 d ago, τ_T=+0.016 τ_DR=+0.013, e=0.62, p_hlr=0.97, REALIZED); 'color' (NOUN, review, seen ×4, last 3.4 d ago, τ_T=+0.020 τ_DR=+0.006, e=0.19, p_hlr=0.95); 'fish' (ADJ, review, seen ×4, last 3.7 d ago, τ_T=+0.050 τ_DR=+0.014, e=0.77, p_hlr=0.95, REALIZED); 'am' (VERB, review, seen ×12, last 11.7 h ago, τ_T=+0.034 τ_DR=+0.023, e=0.99, p_hlr=1.00, REALIZED); 'eats' (VERB, review, seen ×4, last 11.5 h ago, τ_T=+0.024 τ_DR=+0.019, e=0.13, p_hlr=0.99)

**stud_pcorrect** picked: 'doctor' (NOUN, review, seen ×3, last 2.6 d ago, τ_T=+0.046 τ_DR=+0.019, e=0.79, p_hlr=0.95); 'yes' (INTJ, review, seen ×5, last 11.6 h ago, τ_T=+0.082 τ_DR=+0.029, e=0.93, p_hlr=0.99); 'honey' (NOUN, review, seen ×1, last 3.6 d ago, τ_T=-0.000 τ_DR=+0.008, e=0.38, p_hlr=0.85); 'change' (VERB, review, seen ×1, last 2.6 d ago, τ_T=+0.008 τ_DR=+0.008, e=0.51, p_hlr=0.89); 'i' (PRON, review, seen ×64, last 0 min ago, τ_T=+0.052 τ_DR=+0.023, e=1.00, p_hlr=1.00, REALIZED)

**ktcf_flip** picked: 'historical' (ADJ, correction, seen ×3, last 11.4 h ago, τ_T=+0.030 τ_DR=+0.007, e=0.77, p_hlr=0.99); 'the' (DET, correction, seen ×62, last 0 min ago, τ_T=-0.009 τ_DR=+0.018, e=0.99, p_hlr=1.00, REALIZED); 'my' (PRON, correction, seen ×36, last 11.8 h ago, τ_T=+0.033 τ_DR=+0.019, e=0.98, p_hlr=1.00, REALIZED); 'negative' (ADJ, correction, seen ×1, last 4.4 d ago, τ_T=+0.014 τ_DR=-0.006, e=0.61, p_hlr=0.79); 'father' (NOUN, correction, seen ×2, last 4.4 d ago, τ_T=-0.021 τ_DR=-0.006, e=0.55, p_hlr=0.87, REALIZED)

**hlr_lowest** picked: 'negative' (ADJ, correction, seen ×1, last 4.4 d ago, τ_T=+0.014 τ_DR=-0.006, e=0.61, p_hlr=0.79); 'famous' (ADJ, review, seen ×1, last 4.4 d ago, τ_T=+0.033 τ_DR=+0.055, e=0.20, p_hlr=0.82); 'expensive' (ADJ, review, seen ×1, last 4.4 d ago, τ_T=+0.050 τ_DR=+0.153, e=0.25, p_hlr=0.82); 'behind' (ADP, correction, seen ×1, last 3.7 d ago, τ_T=-0.025 τ_DR=+0.003, e=0.27, p_hlr=0.83); 'help' (INTJ, review, seen ×1, last 3.7 d ago, τ_T=+0.019 τ_DR=+0.018, e=0.51, p_hlr=0.84)

**raw_gain** picked: 'a' (DET, review, seen ×22, last 0 min ago, τ_T=+0.103 τ_DR=+0.049, e=0.98, p_hlr=1.00, REALIZED); 'and' (CONJ, review, seen ×18, last 11.7 h ago, τ_T=+0.092 τ_DR=+0.056, e=0.97, p_hlr=1.00); 'yes' (INTJ, review, seen ×5, last 11.6 h ago, τ_T=+0.082 τ_DR=+0.029, e=0.93, p_hlr=0.99); 'fruit' (NOUN, review, seen ×4, last 11.5 h ago, τ_T=+0.071 τ_DR=+0.018, e=0.76, p_hlr=0.99); 'monday' (PROPN, review, seen ×5, last 11.7 h ago, τ_T=+0.071 τ_DR=+0.022, e=0.87, p_hlr=0.99)

**uplift_dr** picked: 'impossible' (ADJ, review, seen ×2, last 4.4 d ago, τ_T=-0.005 τ_DR=+0.163, e=0.93, p_hlr=0.88); 'expensive' (ADJ, review, seen ×1, last 4.4 d ago, τ_T=+0.050 τ_DR=+0.153, e=0.25, p_hlr=0.82); 'white' (ADJ, review, seen ×1, last 3.4 d ago, τ_T=+0.058 τ_DR=+0.064, e=0.08, p_hlr=0.86, REALIZED); 'and' (CONJ, review, seen ×18, last 11.7 h ago, τ_T=+0.092 τ_DR=+0.056, e=0.97, p_hlr=1.00); 'famous' (ADJ, review, seen ×1, last 4.4 d ago, τ_T=+0.033 τ_DR=+0.055, e=0.20, p_hlr=0.82)

**uplift_lcb** picked: 'a' (DET, review, seen ×22, last 0 min ago, τ_T=+0.103 τ_DR=+0.049, e=0.98, p_hlr=1.00, REALIZED); 'and' (CONJ, review, seen ×18, last 11.7 h ago, τ_T=+0.092 τ_DR=+0.056, e=0.97, p_hlr=1.00); 'yes' (INTJ, review, seen ×5, last 11.6 h ago, τ_T=+0.082 τ_DR=+0.029, e=0.93, p_hlr=0.99); 'fruit' (NOUN, review, seen ×4, last 11.5 h ago, τ_T=+0.071 τ_DR=+0.018, e=0.76, p_hlr=0.99); 'very' (ADV, review, seen ×4, last 11.8 h ago, τ_T=+0.069 τ_DR=+0.012, e=0.73, p_hlr=0.99)

**uplift_lcb_area** picked: 'a' (DET, review, seen ×22, last 0 min ago, τ_T=+0.103 τ_DR=+0.049, e=0.98, p_hlr=1.00, REALIZED); 'and' (CONJ, review, seen ×18, last 11.7 h ago, τ_T=+0.092 τ_DR=+0.056, e=0.97, p_hlr=1.00); 'yes' (INTJ, review, seen ×5, last 11.6 h ago, τ_T=+0.082 τ_DR=+0.029, e=0.93, p_hlr=0.99); 'fruit' (NOUN, review, seen ×4, last 11.5 h ago, τ_T=+0.071 τ_DR=+0.018, e=0.76, p_hlr=0.99); 'very' (ADV, review, seen ×4, last 11.8 h ago, τ_T=+0.069 τ_DR=+0.012, e=0.73, p_hlr=0.99)

**uplift_full** picked: 'a' (DET, review, seen ×22, last 0 min ago, τ_T=+0.103 τ_DR=+0.049, e=0.98, p_hlr=1.00, REALIZED); 'and' (CONJ, review, seen ×18, last 11.7 h ago, τ_T=+0.092 τ_DR=+0.056, e=0.97, p_hlr=1.00); 'yes' (INTJ, review, seen ×5, last 11.6 h ago, τ_T=+0.082 τ_DR=+0.029, e=0.93, p_hlr=0.99); 'fruit' (NOUN, review, seen ×4, last 11.5 h ago, τ_T=+0.071 τ_DR=+0.018, e=0.76, p_hlr=0.99); 'very' (ADV, review, seen ×4, last 11.8 h ago, τ_T=+0.069 τ_DR=+0.012, e=0.73, p_hlr=0.99)


## Learner 5 (uid 1259), decision point at token 694 of 839

Last 8 exercises before the decision point (✓ correct, ✗ error):

- day 3.56 [lesson]: i✓ like✓ turkey✓ the✓ potato✗ i✗ need✓ more✓ ice✓ please✓
- day 3.56 [lesson]: a✓ banana✓ i✓ eat✓ a✓ banana✓ a✗ banana✓ bread✓ with✓ butter✓
- day 3.58 [lesson]: the✓ salad✓ has✓ onions✓ i✓ eat✓ a✓ carrot✓ i✓ am✓ hungry✗ we✗ are✗ hungry✗
- day 3.59 [lesson]: more✓ pepper✗ please✓
- day 3.59 [lesson]: good✓ afternoon✓ what✓ time✗ is✗ it✗
- day 3.59 [lesson]: in✓ april✓ the✓ next✓ hour✓ in✓ april✗
- day 3.60 [lesson]: november✓ in✓ july✓ see✗ you✗ in✓ october✗ may✓ is✓ a✓ month✓ in✗ july✗
- day 3.60 [lesson]: i✓ like✓ the✓ fall✓ from✓ september✓ to✗ december✓ from✓ october✗ to✓ december✓ i✓ like✓ winter✓ the✗ spring✓ the✓ season✗

About to do: exercise 7BMbfbG5 (lesson), first token 'the' (DET). Student-model P(correct) = 0.62. What actually happened over the next 5 DET tokens in later exercises: accuracy nan.

Candidate pool: 88 distinct recent tokens (25 corrections, 63 reviews).


**random** picked: 'my' (PRON, review, seen ×27, last 2.3 h ago, τ_T=+0.014 τ_DR=+0.021, e=0.85, p_hlr=1.00, REALIZED); 'hospital' (NOUN, review, seen ×2, last 2.6 h ago, τ_T=+0.001 τ_DR=+0.021, e=0.19, p_hlr=1.00); 'as' (ADP, review, seen ×1, last 1.5 h ago, τ_T=-0.048 τ_DR=-0.801, e=0.47, p_hlr=1.00); 'apples' (NOUN, correction, seen ×1, last 7.4 h ago, τ_T=-0.012 τ_DR=+0.008, e=0.54, p_hlr=0.98); 'why' (ADV, review, seen ×4, last 7.2 h ago, τ_T=+0.033 τ_DR=-0.006, e=0.07, p_hlr=1.00)

**stud_pcorrect** picked: 'november' (PROPN, review, seen ×1, last 9 min ago, τ_T=+0.003 τ_DR=+0.025, e=0.37, p_hlr=1.00); 'good' (ADJ, review, seen ×10, last 17 min ago, τ_T=+0.095 τ_DR=+0.022, e=0.75, p_hlr=1.00, REALIZED); 'red' (VERB, review, seen ×7, last 1.2 h ago, τ_T=-0.030 τ_DR=+0.006, e=0.91, p_hlr=1.00); 'rice' (NOUN, review, seen ×2, last 7.4 h ago, τ_T=+0.064 τ_DR=-0.005, e=0.15, p_hlr=0.99); 'ice' (NOUN, review, seen ×1, last 59 min ago, τ_T=-0.018 τ_DR=+0.004, e=0.52, p_hlr=1.00)

**ktcf_flip** picked: 'july' (PROPN, correction, seen ×2, last 9 min ago, τ_T=+0.030 τ_DR=+0.004, e=0.68, p_hlr=1.00); 'october' (PROPN, correction, seen ×2, last 0 min ago, τ_T=+0.026 τ_DR=+0.011, e=0.36, p_hlr=1.00); 'season' (NOUN, correction, seen ×1, last 0 min ago, τ_T=-0.029 τ_DR=+0.010, e=0.32, p_hlr=1.00); 'apples' (NOUN, correction, seen ×1, last 7.4 h ago, τ_T=-0.012 τ_DR=+0.008, e=0.54, p_hlr=0.98); 'me' (PRON, correction, seen ×2, last 7.2 h ago, τ_T=+0.039 τ_DR=+0.016, e=0.66, p_hlr=0.99)

**hlr_lowest** picked: 'apples' (NOUN, correction, seen ×1, last 7.4 h ago, τ_T=-0.012 τ_DR=+0.008, e=0.54, p_hlr=0.98); 'which' (ADP, review, seen ×1, last 7.2 h ago, τ_T=+0.037 τ_DR=-0.017, e=0.24, p_hlr=0.99); 'me' (PRON, correction, seen ×2, last 7.2 h ago, τ_T=+0.039 τ_DR=+0.016, e=0.66, p_hlr=0.99); 'rice' (NOUN, review, seen ×2, last 7.4 h ago, τ_T=+0.064 τ_DR=-0.005, e=0.15, p_hlr=0.99); 'animals' (NOUN, review, seen ×3, last 7.2 h ago, τ_T=+0.014 τ_DR=+0.010, e=0.20, p_hlr=0.99)

**raw_gain** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.120 τ_DR=+0.057, e=0.84, p_hlr=1.00, REALIZED); 'good' (ADJ, review, seen ×10, last 17 min ago, τ_T=+0.095 τ_DR=+0.022, e=0.75, p_hlr=1.00, REALIZED); 'black' (ADJ, review, seen ×2, last 2.5 h ago, τ_T=+0.073 τ_DR=+0.042, e=0.89, p_hlr=1.00); 'rice' (NOUN, review, seen ×2, last 7.4 h ago, τ_T=+0.064 τ_DR=-0.005, e=0.15, p_hlr=0.99); 'more' (ADJ, review, seen ×5, last 23 min ago, τ_T=+0.060 τ_DR=+0.012, e=0.98, p_hlr=1.00)

**uplift_dr** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.120 τ_DR=+0.057, e=0.84, p_hlr=1.00, REALIZED); 'knee' (NOUN, review, seen ×2, last 2.6 h ago, τ_T=+0.007 τ_DR=+0.051, e=0.21, p_hlr=1.00); 'dinner' (NOUN, review, seen ×6, last 1.3 h ago, τ_T=+0.034 τ_DR=+0.043, e=0.16, p_hlr=1.00); 'black' (ADJ, review, seen ×2, last 2.5 h ago, τ_T=+0.073 τ_DR=+0.042, e=0.89, p_hlr=1.00); 'next' (ADJ, review, seen ×1, last 13 min ago, τ_T=+0.052 τ_DR=+0.032, e=0.66, p_hlr=1.00)

**uplift_lcb** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.120 τ_DR=+0.057, e=0.84, p_hlr=1.00, REALIZED); 'good' (ADJ, review, seen ×10, last 17 min ago, τ_T=+0.095 τ_DR=+0.022, e=0.75, p_hlr=1.00, REALIZED); 'black' (ADJ, review, seen ×2, last 2.5 h ago, τ_T=+0.073 τ_DR=+0.042, e=0.89, p_hlr=1.00); 'rice' (NOUN, review, seen ×2, last 7.4 h ago, τ_T=+0.064 τ_DR=-0.005, e=0.15, p_hlr=0.99); 'more' (ADJ, review, seen ×5, last 23 min ago, τ_T=+0.060 τ_DR=+0.012, e=0.98, p_hlr=1.00)

**uplift_lcb_area** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.120 τ_DR=+0.057, e=0.84, p_hlr=1.00, REALIZED); 'good' (ADJ, review, seen ×10, last 17 min ago, τ_T=+0.095 τ_DR=+0.022, e=0.75, p_hlr=1.00, REALIZED); 'rice' (NOUN, review, seen ×2, last 7.4 h ago, τ_T=+0.064 τ_DR=-0.005, e=0.15, p_hlr=0.99); 'are' (VERB, correction, seen ×7, last 39 min ago, τ_T=+0.039 τ_DR=+0.028, e=0.90, p_hlr=1.00, REALIZED); 'me' (PRON, correction, seen ×2, last 7.2 h ago, τ_T=+0.039 τ_DR=+0.016, e=0.66, p_hlr=0.99)

**uplift_full** picked: 'a' (DET, review, seen ×20, last 9 min ago, τ_T=+0.120 τ_DR=+0.057, e=0.84, p_hlr=1.00, REALIZED); 'good' (ADJ, review, seen ×10, last 17 min ago, τ_T=+0.095 τ_DR=+0.022, e=0.75, p_hlr=1.00, REALIZED); 'rice' (NOUN, review, seen ×2, last 7.4 h ago, τ_T=+0.064 τ_DR=-0.005, e=0.15, p_hlr=0.99); 'are' (VERB, correction, seen ×7, last 39 min ago, τ_T=+0.039 τ_DR=+0.028, e=0.90, p_hlr=1.00, REALIZED); 'me' (PRON, correction, seen ×2, last 7.2 h ago, τ_T=+0.039 τ_DR=+0.016, e=0.66, p_hlr=0.99)
