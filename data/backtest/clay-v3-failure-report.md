# Clay ML v3 Failure Report

The Phase B residual model failed at least one locked 2024 hold-out gate. Clay ML is dead for this design cycle; no signal wiring is authorised.

```text
Clay ML v3 hold-out report
===========================
model_version: clay-v3
training_years: [2022, 2023]
test_year: 2024
n_test: 682
lambda_selected: 10.0
alpha: -0.0451541159396
beta_ta_surface_speed: -0.0991301235043 mean=0.766031007752 std=0.158219450092
beta_altitude_m: 0.0369167010227 mean=263.863565891 std=302.956353174
beta_temp_mean_c: -0.0368458443225 mean=17.8187596899 std=4.7604170568

Gate metrics
metric,v3,pinnacle,delta_pin_minus_v3,gate,status
log_loss,0.612353,0.614088,0.001735,>=0.005 abs OR >=1.0% rel (0.28%),FAIL
brier,0.212480,0.213289,0.000809,>=0.002,FAIL
ece,0.031401,0.036298,0.004897,<=0.035 and <=pinnacle_ece,PASS
worst_month_stability,,,,not worse than pinnacle +0.005,PASS

Per-month log-loss
month,n,v3,pinnacle,delta_pin_minus_v3,status
2,93,0.648096,0.658987,0.010891,PASS
3,6,0.866999,0.751216,-0.115783,PASS
4,309,0.593263,0.596536,0.003272,PASS
5,144,0.618199,0.615037,-0.003163,PASS
7,130,0.613927,0.616307,0.002379,PASS

Per-tournament log-loss
tournament,n,v3,pinnacle,delta_pin_minus_v3
argentina_open,26,0.697519,0.696598,-0.000921
barcelona_open,41,0.595427,0.600791,0.005364
bmw_open,27,0.561473,0.565979,0.004506
chile_open,24,0.629742,0.647578,0.017837
cordoba_open,21,0.693411,0.683003,-0.010408
croatia_open,27,0.613611,0.613347,-0.000264
estoril_open,27,0.617070,0.625203,0.008134
european_open,26,0.557268,0.569262,0.011995
generali_open,24,0.603834,0.602227,-0.001608
geneva_open,26,0.602403,0.602806,0.000402
grand_prix_hassan_ii,24,0.605390,0.606247,0.000858
internazionali_bnl_ditalia,91,0.610354,0.609105,-0.001248
lyon_open,23,0.642713,0.634676,-0.008037
monte_carlo_masters,53,0.561505,0.560613,-0.000892
mutua_madrid_open,88,0.598589,0.592748,-0.005841
nordea_open,27,0.753441,0.752655,-0.000786
rio_open,28,0.630857,0.635593,0.004735
suisse_open_gstaad,26,0.535354,0.537830,0.002476
tiriac_open,27,0.609267,0.635925,0.026658
us_mens_clay_court_championships,26,0.642451,0.646428,0.003977

Calibration curve - p_v3 equal-width bins
bin,lo,hi,n,pred,observed
1,0.0,0.1,5,0.070107,0.000000
2,0.1,0.2,36,0.163477,0.138889
3,0.2,0.3,62,0.253404,0.241935
4,0.3,0.4,111,0.352439,0.324324
5,0.4,0.5,124,0.443947,0.508065
6,0.5,0.6,139,0.553526,0.568345
7,0.6,0.7,107,0.645425,0.644860
8,0.7,0.8,61,0.747432,0.819672
9,0.8,0.9,30,0.843283,0.800000
10,0.9,1.0,7,0.918312,1.000000

overall_status: FAIL
decision: clay ML v3 failed the locked hold-out gates; no signal wiring is authorised.
```
