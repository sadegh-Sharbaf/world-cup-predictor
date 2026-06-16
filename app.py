
import json
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

APP_TITLE = "World Cup 2026 Predictor"
DB_PATH = Path("worldcup_bets.db")
FIXTURES_PATH = Path("fixtures.json")

st.set_page_config(page_title=APP_TITLE, page_icon="🏆", layout="wide")

st.markdown(
    """
    <style>
        .stApp {
            background: radial-gradient(circle at top, #14213d 0%, #0b132b 45%, #09111f 100%);
            color: #f8fafc;
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3, h4 {
            color: #fca311 !important;
            font-weight: 800 !important;
            letter-spacing: 0.3px;
        }
        p, label, .stMarkdown, .stDataFrame {
            color: #e5e7eb;
        }
        div[data-testid="stMetricValue"] {
            color: #fca311;
        }
        .glass {
            background: rgba(20, 33, 61, 0.72);
            border: 1px solid rgba(252, 163, 17, 0.20);
            border-radius: 18px;
            padding: 16px 18px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.24);
            margin-bottom: 14px;
            backdrop-filter: blur(10px);
        }
        .match-title {
            font-size: 1.2rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 6px;
        }
        .match-meta {
            color: #cbd5e1;
            font-size: 0.95rem;
            line-height: 1.8;
        }
        .score-pill {
            display: inline-block;
            background: rgba(252, 163, 17, 0.14);
            border: 1px solid rgba(252, 163, 17, 0.35);
            color: #fca311;
            padding: 4px 10px;
            border-radius: 999px;
            font-weight: 700;
            margin-right: 8px;
            margin-bottom: 6px;
        }
        .stButton > button {
            border-radius: 12px;
            border: 1px solid rgba(252, 163, 17, 0.55);
            background: #fca311;
            color: #0b132b;
            font-weight: 800;
            width: 100%;
        }
        .stButton > button:hover {
            background: #ffd166;
            color: #0b132b;
            border-color: #ffd166;
        }
        .stTextInput input, .stNumberInput input, .stSelectbox div, .stDateInput input, .stTimeInput input {
            border-radius: 10px !important;
        }
        div[data-baseweb="tab-list"] button {
            color: #f8fafc !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------
# Database
# ----------------------------
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            kickoff TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled',
            home_score INTEGER,
            away_score INTEGER,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(home_team, away_team, kickoff)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            match_id INTEGER NOT NULL,
            predicted_home INTEGER NOT NULL,
            predicted_away INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_name, match_id),
            FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


def load_fixture_catalog() -> pd.DataFrame:
    if not FIXTURES_PATH.exists():
        return pd.DataFrame(columns=["match_no", "stage", "home_team", "away_team", "kickoff", "venue"])

    with FIXTURES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    expected = ["match_no", "stage", "home_team", "away_team", "kickoff", "venue"]
    for col in expected:
        if col not in df.columns:
            df[col] = None
    return df[expected]


def seed_matches_from_json() -> None:
    catalog = load_fixture_catalog()
    if catalog.empty:
        return

    conn = get_conn()
    cur = conn.cursor()

    for _, row in catalog.iterrows():
        cur.execute(
            """
            INSERT OR IGNORE INTO matches (home_team, away_team, kickoff, status, source)
            VALUES (?, ?, ?, ?, 'json')
            """,
            (
                str(row["home_team"]).strip(),
                str(row["away_team"]).strip(),
                str(row["kickoff"]).strip(),
                "scheduled",
            ),
        )

    conn.commit()
    conn.close()


def reset_to_json_fixtures() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM bets")
    cur.execute("DELETE FROM matches")
    conn.commit()
    conn.close()
    seed_matches_from_json()


def upsert_match(
    home_team: str,
    away_team: str,
    kickoff: str,
    status: str = "scheduled",
    home_score: Optional[int] = None,
    away_score: Optional[int] = None,
    source: str = "manual",
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO matches (
            home_team, away_team, kickoff, status, home_score, away_score, source, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(home_team, away_team, kickoff) DO UPDATE SET
            status=excluded.status,
            home_score=excluded.home_score,
            away_score=excluded.away_score,
            source=excluded.source,
            updated_at=CURRENT_TIMESTAMP
        """,
        (home_team.strip(), away_team.strip(), kickoff.strip(), status, home_score, away_score, source),
    )
    conn.commit()
    conn.close()


def update_match_result(match_id: int, status: str, home_score: int, away_score: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE matches
        SET status=?, home_score=?, away_score=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (status, home_score, away_score, match_id),
    )
    conn.commit()
    conn.close()


def delete_match(match_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM bets WHERE match_id=?", (match_id,))
    cur.execute("DELETE FROM matches WHERE id=?", (match_id,))
    conn.commit()
    conn.close()


def clear_all_data() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM bets")
    cur.execute("DELETE FROM matches")
    conn.commit()
    conn.close()


def save_prediction(player_name: str, match_id: int, predicted_home: int, predicted_away: int) -> Tuple[bool, str]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO bets (player_name, match_id, predicted_home, predicted_away)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(player_name, match_id) DO UPDATE SET
                predicted_home=excluded.predicted_home,
                predicted_away=excluded.predicted_away,
                created_at=CURRENT_TIMESTAMP
            """,
            (player_name.strip(), match_id, predicted_home, predicted_away),
        )
        conn.commit()
        return True, "Prediction saved."
    except Exception as exc:
        return False, f"Could not save prediction: {exc}"
    finally:
        conn.close()


@st.cache_data(ttl=5)
def load_matches() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT id, home_team, away_team, kickoff, status, home_score, away_score, source, created_at, updated_at
        FROM matches
        ORDER BY
            CASE status
                WHEN 'live' THEN 0
                WHEN 'scheduled' THEN 1
                WHEN 'finished' THEN 2
                ELSE 3
            END,
            kickoff ASC,
            id ASC
        """,
        conn,
    )
    conn.close()

    catalog = load_fixture_catalog()
    if not catalog.empty and not df.empty:
        catalog = catalog.rename(
            columns={
                "home_team": "home_team_cat",
                "away_team": "away_team_cat",
                "kickoff": "kickoff_cat",
            }
        )
        df = df.merge(
            catalog,
            how="left",
            left_on=["home_team", "away_team", "kickoff"],
            right_on=["home_team_cat", "away_team_cat", "kickoff_cat"],
        )
        df = df.drop(columns=[c for c in ["home_team_cat", "away_team_cat", "kickoff_cat"] if c in df.columns])

    elif not catalog.empty and df.empty:
        # no-op; caller will see empty dataframe
        pass

    return df


@st.cache_data(ttl=5)
def load_bets() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT
            b.id,
            b.player_name,
            b.match_id,
            b.predicted_home,
            b.predicted_away,
            b.created_at,
            m.home_team,
            m.away_team,
            m.kickoff,
            m.status,
            m.home_score,
            m.away_score
        FROM bets b
        JOIN matches m ON m.id = b.match_id
        ORDER BY b.created_at DESC, b.id DESC
        """,
        conn,
    )
    conn.close()
    return df


def invalidate_cache() -> None:
    load_matches.clear()
    load_bets.clear()


# ----------------------------
# Scoring
# ----------------------------
def outcome(h: int, a: int) -> str:
    if h > a:
        return "H"
    if h < a:
        return "A"
    return "D"


def calculate_points(pred_home: int, pred_away: int, real_home: int, real_away: int) -> int:
    if pred_home == real_home and pred_away == real_away:
        return 5
    if outcome(pred_home, pred_away) == outcome(real_home, real_away):
        return 2
    return 0


def leaderboard_df() -> pd.DataFrame:
    bets = load_bets()
    if bets.empty:
        return pd.DataFrame(columns=["Rank", "Player", "Points", "Exact Picks", "Correct Outcome Picks"])

    points = []
    exact = []
    outcome_hits = []

    for _, row in bets.iterrows():
        if pd.isna(row["home_score"]) or pd.isna(row["away_score"]):
            pts = 0
            exact_hit = 0
            outcome_hit = 0
        else:
            real_home = int(row["home_score"])
            real_away = int(row["away_score"])
            pred_home = int(row["predicted_home"])
            pred_away = int(row["predicted_away"])
            pts = calculate_points(pred_home, pred_away, real_home, real_away)
            exact_hit = int(pred_home == real_home and pred_away == real_away)
            outcome_hit = int(outcome(pred_home, pred_away) == outcome(real_home, real_away))

        points.append(pts)
        exact.append(exact_hit)
        outcome_hits.append(outcome_hit)

    bets = bets.assign(points=points, exact=exact, outcome_hit=outcome_hits)

    grouped = (
        bets.groupby("player_name", as_index=False)
        .agg(
            Points=("points", "sum"),
            Exact_Picks=("exact", "sum"),
            Correct_Outcome_Picks=("outcome_hit", "sum"),
        )
        .sort_values(
            ["Points", "Exact_Picks", "Correct_Outcome_Picks", "player_name"],
            ascending=[False, False, False, True],
        )
        .reset_index(drop=True)
    )

    grouped.insert(0, "Rank", range(1, len(grouped) + 1))
    grouped.rename(
        columns={
            "player_name": "Player",
            "Exact_Picks": "Exact Picks",
            "Correct_Outcome_Picks": "Correct Outcome Picks",
        },
        inplace=True,
    )
    return grouped


# ----------------------------
# UI helpers
# ----------------------------
def status_label(status: str) -> str:
    return {
        "scheduled": "Scheduled",
        "live": "Live",
        "finished": "Finished",
    }.get(status, status.title())


def score_text(row: pd.Series) -> str:
    if pd.isna(row["home_score"]) or pd.isna(row["away_score"]):
        return "-"
    return f"{int(row['home_score'])} - {int(row['away_score'])}"


def match_label(row: pd.Series) -> str:
    parts = []
    if "match_no" in row and pd.notna(row["match_no"]):
        parts.append(f"M{int(row['match_no'])}")
    if "stage" in row and pd.notna(row["stage"]):
        parts.append(str(row["stage"]))
    return " · ".join(parts) if parts else "Match"


def render_match_card(row: pd.Series) -> None:
    kickoff = row["kickoff"] or "TBA"
    venue = row["venue"] if "venue" in row and pd.notna(row["venue"]) else "TBA"
    st.markdown(
        f"""
        <div class="glass">
            <div class="match-title">⚽ {row["home_team"]} vs {row["away_team"]}</div>
            <div class="match-meta">
                <span class="score-pill">{match_label(row)}</span>
                <span class="score-pill">{status_label(row["status"])}</span>
                <span class="score-pill">Kickoff: {kickoff}</span>
                <span class="score-pill">Venue: {venue}</span>
                <span class="score-pill">Score: {score_text(row)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def as_int(val) -> int:
    return int(val) if val is not None and not pd.isna(val) else 0


# ----------------------------
# App
# ----------------------------
init_db()
seed_matches_from_json()

st.title("🏆 World Cup 2026 Predictor")
st.caption("A fast, no-login prediction app. Fixtures are loaded from fixtures.json and can be edited manually later.")

with st.sidebar:
    st.header("Control Panel")
    player_name = st.text_input("Your name", value="Sadegh", help="No login needed. Use the same name every time.")
    st.caption("Fixtures come from the local JSON file, so deployment on free hosting stays simple.")

    st.divider()
    st.subheader("Data")
    if st.button("Reload fixtures from JSON"):
        reset_to_json_fixtures()
        invalidate_cache()
        st.success("Fixtures reloaded from JSON.")
        st.rerun()

    if st.button("Refresh data"):
        invalidate_cache()
        st.rerun()

    if st.button("Reset all data"):
        clear_all_data()
        seed_matches_from_json()
        invalidate_cache()
        st.warning("All predictions and matches were reset, then the JSON fixtures were loaded again.")
        st.rerun()

tab_matches, tab_add, tab_leaderboard, tab_predictions, tab_admin = st.tabs(
    ["Matches", "Add Match", "Leaderboard", "Predictions", "Admin"]
)

with tab_matches:
    matches = load_matches()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Matches", len(matches))
    col_b.metric("Live", int((matches["status"] == "live").sum()) if not matches.empty else 0)
    col_c.metric("Finished", int((matches["status"] == "finished").sum()) if not matches.empty else 0)

    if matches.empty:
        st.info("No matches yet. Reload fixtures from JSON in the sidebar.")
    else:
        for _, row in matches.iterrows():
            render_match_card(row)

            if row["status"] == "scheduled":
                with st.form(key=f"bet_form_{row['id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        pred_home = st.number_input(
                            f"{row['home_team']} goals",
                            min_value=0,
                            max_value=20,
                            value=0,
                            step=1,
                            key=f"pred_home_{row['id']}",
                        )
                    with c2:
                        pred_away = st.number_input(
                            f"{row['away_team']} goals",
                            min_value=0,
                            max_value=20,
                            value=0,
                            step=1,
                            key=f"pred_away_{row['id']}",
                        )

                    submitted = st.form_submit_button("Save prediction")
                    if submitted:
                        if not player_name.strip():
                            st.warning("Please enter a name in the sidebar.")
                        else:
                            ok, msg = save_prediction(player_name, int(row["id"]), as_int(pred_home), as_int(pred_away))
                            if ok:
                                invalidate_cache()
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
            elif row["status"] == "live":
                st.info("This match is live. Predictions are locked.")
            else:
                if pd.notna(row["home_score"]) and pd.notna(row["away_score"]):
                    st.success(f"Final result: {int(row['home_score'])}-{int(row['away_score'])}")

            st.markdown("---")

with tab_add:
    st.subheader("Add a match manually")
    st.write("Use this for extra fixtures or custom games.")

    with st.form("add_match_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            home_team = st.text_input("Home team", value="Argentina")
            kickoff = st.text_input("Kickoff", value="2026-06-30 20:00", help="Format: YYYY-MM-DD HH:MM")
        with c2:
            away_team = st.text_input("Away team", value="Brazil")
            status = st.selectbox("Status", ["scheduled", "live", "finished"], index=0)
        with c3:
            home_score = st.number_input("Home score", min_value=0, max_value=20, value=0, step=1)
            away_score = st.number_input("Away score", min_value=0, max_value=20, value=0, step=1)

        add_submit = st.form_submit_button("Add / update match")
        if add_submit:
            if not home_team.strip() or not away_team.strip() or not kickoff.strip():
                st.warning("Home team, away team, and kickoff are required.")
            else:
                hs = as_int(home_score) if status == "finished" else None
                aw = as_int(away_score) if status == "finished" else None
                upsert_match(
                    home_team=home_team,
                    away_team=away_team,
                    kickoff=kickoff,
                    status=status,
                    home_score=hs,
                    away_score=aw,
                    source="manual",
                )
                invalidate_cache()
                st.success("Match saved.")
                st.rerun()

    st.markdown("### Update a final result")
    matches_df = load_matches()
    if matches_df.empty:
        st.info("Add a match first.")
    else:
        options = {
            f'#{int(r.id)} — {r.home_team} vs {r.away_team} ({r.kickoff})': int(r.id)
            for _, r in matches_df.iterrows()
        }
        selected = st.selectbox("Choose a match", list(options.keys()))
        selected_id = options[selected]

        sel_row = matches_df[matches_df["id"] == selected_id].iloc[0]
        with st.form("result_form"):
            r1, r2, r3 = st.columns(3)
            with r1:
                new_status = st.selectbox(
                    "Status",
                    ["scheduled", "live", "finished"],
                    index=["scheduled", "live", "finished"].index(sel_row["status"]),
                )
            with r2:
                real_home = st.number_input("Home score", min_value=0, max_value=20, value=as_int(sel_row["home_score"]), step=1)
            with r3:
                real_away = st.number_input("Away score", min_value=0, max_value=20, value=as_int(sel_row["away_score"]), step=1)

            save_result = st.form_submit_button("Save result")
            if save_result:
                update_match_result(int(selected_id), new_status, as_int(real_home), as_int(real_away))
                invalidate_cache()
                st.success("Result updated.")
                st.rerun()

with tab_leaderboard:
    st.subheader("Leaderboard")
    lb = leaderboard_df()
    if lb.empty:
        st.info("No predictions yet.")
    else:
        st.dataframe(lb, use_container_width=True, hide_index=True)

    st.markdown("### Scoring rules")
    st.write("Exact score = 5 points")
    st.write("Correct outcome = 2 points")
    st.write("Wrong prediction = 0 points")

with tab_predictions:
    st.subheader("All predictions")
    bets = load_bets()
    if bets.empty:
        st.info("No predictions have been saved yet.")
    else:
        bets = bets.copy()
        bets["Prediction"] = bets["predicted_home"].astype(str) + " - " + bets["predicted_away"].astype(str)
        bets["Actual"] = bets.apply(
            lambda r: "-" if pd.isna(r["home_score"]) or pd.isna(r["away_score"]) else f"{int(r['home_score'])} - {int(r['away_score'])}",
            axis=1,
        )
        bets["Points"] = bets.apply(
            lambda r: 0 if pd.isna(r["home_score"]) or pd.isna(r["away_score"]) else calculate_points(
                int(r["predicted_home"]), int(r["predicted_away"]), int(r["home_score"]), int(r["away_score"])
            ),
            axis=1,
        )
        show = bets[["player_name", "home_team", "away_team", "Prediction", "Actual", "Points", "status", "created_at"]]
        show.columns = ["Player", "Home", "Away", "Prediction", "Actual", "Points", "Status", "Created"]
        st.dataframe(show, use_container_width=True, hide_index=True)

with tab_admin:
    st.subheader("Database snapshot")
    st.caption("Small admin view for quick debugging and manual cleanup.")
    c1, c2 = st.columns(2)
    with c1:
        st.write("Matches")
        st.dataframe(load_matches(), use_container_width=True, hide_index=True)
    with c2:
        st.write("Bets")
        st.dataframe(load_bets(), use_container_width=True, hide_index=True)

    st.markdown("### Delete a match")
    matches_df = load_matches()
    if not matches_df.empty:
        del_options = {
            f"#{int(r.id)} — {r.home_team} vs {r.away_team} ({r.kickoff})": int(r.id)
            for _, r in matches_df.iterrows()
        }
        selected_del = st.selectbox("Select match to delete", list(del_options.keys()), key="delete_match_select")
        if st.button("Delete selected match"):
            delete_match(del_options[selected_del])
            invalidate_cache()
            st.warning("Match deleted.")
            st.rerun()

    st.markdown("### Danger zone")
    if st.button("Clear everything and reseed"):
        reset_to_json_fixtures()
        invalidate_cache()
        st.warning("All data reset and fixtures reloaded from JSON.")
        st.rerun()

st.caption("Tip: use a consistent player name so the leaderboard stays meaningful.")
