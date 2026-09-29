import io

import pandas as pd
import streamlit as st

st.set_page_config(page_title="PB Financing Cost Optimiser", layout="wide")

# ---------- Sample data (used until files are uploaded) ----------
SAMPLE_RATES = pd.DataFrame({
    "pb": ["PB_A", "PB_B", "PB_C"],
    "long_spread_bps": [45, 38, 50],   # long financing spread
    "short_fee_bps": [30, 35, 25],     # short borrow fee
})

SAMPLE_POSITIONS = pd.DataFrame({
    "ticker": ["AAA", "BBB", "CCC", "DDD", "EEE"],
    "side": ["long", "long", "short", "long", "short"],
    "notional_usd": [50_000_000, 30_000_000, 20_000_000, 40_000_000, 15_000_000],
})

RATES_COLUMNS = {"pb", "long_spread_bps", "short_fee_bps"}
POSITIONS_COLUMNS = {"ticker", "side", "notional_usd"}


# ---------- Core calculation (same logic as the notebook) ----------
def calculate(rates, positions):
    positions = positions.copy()
    positions["side"] = positions["side"].str.strip().str.lower()

    combo = positions.merge(rates, how="cross")
    combo["rate_bps"] = combo["long_spread_bps"].where(
        combo["side"] == "long", combo["short_fee_bps"])
    combo["annual_cost_usd"] = combo["notional_usd"] * combo["rate_bps"] / 10_000

    best = combo.loc[combo.groupby("ticker")["annual_cost_usd"].idxmin()]
    single_pb = combo.groupby("pb")["annual_cost_usd"].sum()
    return combo, best, single_pb


# ---------- Page ----------
st.title("PB Financing Cost Optimiser")
st.write(
    "Upload today's PB rate card and positions to see which prime broker is "
    "cheapest for each position, and how much that saves versus using one PB. "
    "Mock data only."
)

st.sidebar.header("Today's files")
rates_file = st.sidebar.file_uploader("Rates CSV", type="csv")
positions_file = st.sidebar.file_uploader("Positions CSV", type="csv")
st.sidebar.caption(
    "Rates need columns: pb, long_spread_bps, short_fee_bps. "
    "Positions need: ticker, side, notional_usd."
)

rates = pd.read_csv(rates_file) if rates_file else SAMPLE_RATES
positions = pd.read_csv(positions_file) if positions_file else SAMPLE_POSITIONS

if not (rates_file and positions_file):
    st.info("Showing sample data. Upload both CSVs in the sidebar to run on your own files.")

missing_rates = RATES_COLUMNS - set(rates.columns)
missing_positions = POSITIONS_COLUMNS - set(positions.columns)
if missing_rates or missing_positions:
    if missing_rates:
        st.error(f"Rates file is missing columns: {', '.join(sorted(missing_rates))}")
    if missing_positions:
        st.error(f"Positions file is missing columns: {', '.join(sorted(missing_positions))}")
    st.stop()

combo, best, single_pb = calculate(rates, positions)

optimised = best["annual_cost_usd"].sum()
best_single_name = single_pb.idxmin()
best_single_cost = single_pb.min()
saving = best_single_cost - optimised
saving_bps = saving / positions["notional_usd"].sum() * 10_000

# Headline numbers
col1, col2, col3 = st.columns(3)
col1.metric("Optimised annual cost", f"${optimised:,.0f}")
col2.metric(f"Cheapest single PB ({best_single_name})", f"${best_single_cost:,.0f}")
col3.metric("Annual saving", f"${saving:,.0f}", f"{saving_bps:.1f} bps of notional")

# Best allocation and chart
left, right = st.columns(2)

with left:
    st.subheader("Cheapest PB for each position")
    st.dataframe(
        best[["ticker", "side", "notional_usd", "pb", "rate_bps", "annual_cost_usd"]]
        .rename(columns={"pb": "best_pb"}),
        hide_index=True,
        width="stretch",
    )

with right:
    st.subheader("Total cost by allocation")
    compare = single_pb.copy()
    compare["Optimised"] = optimised
    st.bar_chart(compare.rename("annual_cost_usd"))

# Full detail
with st.expander("Full cost matrix and inputs"):
    st.write("Annual cost of each position at each PB (USD)")
    st.dataframe(
        combo.pivot(index="ticker", columns="pb", values="annual_cost_usd"),
        width="stretch",
    )
    st.write("Rates")
    st.dataframe(rates, hide_index=True)
    st.write("Positions")
    st.dataframe(positions, hide_index=True)

# Excel download
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    compare.to_frame("annual_cost_usd").to_excel(writer, sheet_name="Summary")
    best.to_excel(writer, sheet_name="Best_Allocation", index=False)
    combo.to_excel(writer, sheet_name="All_Costs", index=False)
    rates.to_excel(writer, sheet_name="Rates", index=False)
    positions.to_excel(writer, sheet_name="Positions", index=False)

st.download_button(
    "Download Excel report",
    data=buffer.getvalue(),
    file_name="financing_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
