"""Northgate findings v0 — every headline number in one reproducible pass.
Run: python3 findings_v0.py  (reads ../northgate/packet/data)
Each finding returns: annual run-rate (gross), FY2026 realistic, one-time, and the rows/docs it rests on."""
import pandas as pd, json
D = "/home/claude/northgate/packet/data/"
r = lambda f: pd.read_csv(D + f)
ops, proc, cm, cd = r("operations-monthly.csv"), r("procedures-monthly.csv"), r("claims-monthly.csv"), r("claim-denials.csv")
po, ap, pp, ben, emp = r("purchase-orders.csv"), r("ap-ledger.csv"), r("payment-processing.csv"), r("benefits-enrollment.csv"), r("employees.csv")
wl, na, su, vs = r("denial-worklog.csv"), r("network-activity.csv"), r("software-usage.csv"), r("vendor-spend.csv")
NET = 0.78; CM = 0.72
SLIP = ["NGD-12", "NGD-16", "NGD-17", "NGD-18", "NGD-19", "NGD-20", "NGD-21", "NGD-22"]
out = {}

# 1 Charge capture leakage at the 8 routing-slip sites (excess over the 14 digital sites' baseline gap)
proc["gap"] = proc.procedures_completed - proc.procedures_submitted_to_claim
dig = proc[~proc.practice_id.isin(SLIP)]; base = dig.gap.sum() / dig.procedures_completed.sum()
s = proc[proc.practice_id.isin(SLIP)].copy(); s["excess_val"] = (s.gap - s.procedures_completed * base) * s.avg_procedure_value_usd
out["charge_capture"] = dict(baseline_gap_pct=round(base * 100, 3), excess_production=round(s.excess_val.sum()), annual_net=round(s.excess_val.sum() * NET),
                             rows="procedures-monthly.csv: 96 rows (8 sites x 12 mo)", docs="2025-05-20 IT sync (Tom); employees.csv Billing Entry Clerk duties; SOP 1.2-1.3")

# 2 Denial queue: same claims lost, but lowest-value first (row-average model)
cd["avg"] = cd.denied_amount_usd / cd.denied_claims; cd["wo_amt"] = cd.avg * cd.written_off_past_filing_limit
q = cd[cd.denial_reason != "Provider not credentialed with payer"]; q = q.loc[q.index.repeat(q.denied_claims)].sort_values("avg")
n = int(cd.written_off_past_filing_limit.sum()); saved = cd.wo_amt.sum() - q.avg.iloc[:n].sum()
out["denial_priority"] = dict(writeoffs_today=round(cd.wo_amt.sum()), claims_lost=n, billed_saved=round(saved), annual_net=round(saved * 0.794),
                              rows="claim-denials.csv (10,126 rows)", docs="SOP 3.2-3.4 FIFO; appendix s4; P&L denial write-offs $1,300,095")

# 3 Osei / Delta credentialing hold (one-time, deadline-bound)
o = cd[cd.denial_reason == "Provider not credentialed with payer"]
out["osei_retro_bill"] = dict(claims=int(o.denied_claims.sum()), billed=round(o.denied_amount_usd.sum()), expected_cash=round(o.denied_amount_usd.sum() * 0.857),
                              deadline="365 days from DOS: 2026-03-14 .. 2026-08-21", rows="claim-denials.csv NGD-13 Delta Mar-Aug 2025; provider-roster PROV-024", docs="2025-11-06 Toledo thread")

# 4 Supply rebates
hs, pat = po[po.distributor == "Henry Schein"].amount_usd.sum(), po[po.distributor == "Patterson Dental"].amount_usd.sum()
def tier_hs(x): return 0.055 if x >= 2.5e6 else 0.04 if x >= 1.75e6 else 0.025 if x >= 1e6 else 0
def tier_pat(x): return 0.05 if x >= 2.5e6 else 0.04 if x >= 1.75e6 else 0.025 if x >= 1e6 else 0
po["q"] = pd.to_datetime(po.order_date).dt.quarter
out["rebates"] = dict(hs=round(hs), patterson=round(pat), earned_split=round(hs * tier_hs(hs) + pat * tier_pat(pat)), collected=0,
                      consolidated_hs=round((hs + pat) * tier_hs(hs + pat)), consolidated_pat=round((hs + pat) * tier_pat(hs + pat)),
                      fy25_still_claimable=round(po[(po.distributor == "Henry Schein") & (po.q == 4)].amount_usd.sum() * 0.025 + pat * 0.025),
                      rows="purchase-orders.csv (1,860 rows)", docs="HS s7.2-7.4 (quarterly HS-VR-4, 45 days); Patterson (annual cert, 60 days); 2025-07-22 Renata email")

# 5 Ghost cost centers + Dayton retainer
g = ap[ap.practice_id.isin(["NGD-23", "NGD-24"])]; h = ap[ap.vendor == "Halstead Creative Group"]
out["ghost_sites"] = dict(ngd23_24=round(g.amount_usd.sum(), 2), halstead_dayton=round(h.amount_usd.sum(), 2), total=round(g.amount_usd.sum() + h.amount_usd.sum()),
                          rows="ap-ledger.csv: 120 NGD-23/24 rows + 12 Halstead rows", docs="2025-10-14 Nash/Renata emails; Spectrum/Vector/Halstead scanned invoices")

# 6 Benefits: duplicate legacy plans (+ sub-30h enrollees, reported separately)
leg = ben[ben.plan_id.str.startswith("LEG")]
e = ben[~ben.plan_id.str.startswith("LEG")].merge(emp[["employee_id", "fte"]], on="employee_id"); sub30 = e[e.fte * 40 < 30]
out["benefits"] = dict(legacy_people=int(leg.employee_id.nunique()), legacy_annual=round(leg.monthly_employer_premium_usd.sum() * 12),
                       sellers=sorted(leg.sponsoring_entity.unique()), sub30_people=len(sub30), sub30_annual=round(sub30.monthly_employer_premium_usd.sum() * 12),
                       rows="benefits-enrollment.csv (18 LEG rows; 17 sub-30h rows)", docs="2025-08-19 Dee email; benefits policy; appendix s10")

# 7 Card processing
t = pp.groupby("processor")[["volume_usd", "fees_usd"]].sum(); best = t.loc["Sunbit Merchant"].fees_usd / t.loc["Sunbit Merchant"].volume_usd
out["processing"] = dict(rates={k: round(v.fees_usd / v.volume_usd * 100, 3) for k, v in t.iterrows()},
                         annual=round(sum(v.fees_usd - v.volume_usd * best for k, v in t.iterrows())), rows="payment-processing.csv (264 rows); vendor-spend Sunbit SaaS at 22 sites", docs="2025-04-09 Nash email")

# 8 Backfill (assumption-heavy; appendix 40% fill)
ops["open"] = ops.no_shows + ops.late_cancellations; ops["ppa"] = ops.gross_production_usd / ops.appointments_completed
prod = (ops.open * 0.40 * ops.ppa).sum()
out["backfill"] = dict(openings=int(ops.open.sum()), production_at_40pct=round(prod), contribution=round(prod * NET * CM), rows="operations-monthly.csv (264 rows)", docs="appendix s6 (40% fill assumption)")

# 9 People: the telemetry trap
w = wl.groupby("employee_id").agg(claims=("claims_worked", "sum"), dollars=("amount_recovered_usd", "sum"))
w["per_claim"] = w.dollars / w.claims
out["people"] = dict(marguerite=w.loc["E-0300"].round(0).to_dict(), onsite_hrs_mo=round(na[na.employee_id == "E-0300"].onsite_network_hours.mean(), 1),
                     team_median_dollars=round(w.dollars.median()), queue_specialists=w.loc[["E-0304", "E-0307"]].round(0).to_dict("index"))

print(json.dumps(out, indent=1, default=str))
