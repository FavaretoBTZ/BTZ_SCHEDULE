# app.py
# Streamlit schedule tracker — auto-refresh 1s, fuso fixo Brasília.
# >>> Agora com campos de Início e Fim editáveis com SEGUNDOS (HH:MM:SS).

from __future__ import annotations
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import re

# ---------- Config ----------
st.set_page_config(
    page_title="BTZ | Cronograma de Pista",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ_NAME = "America/Sao_Paulo"     # sempre Brasília
TZINFO = ZoneInfo(TZ_NAME)

STATUS_DONE = "Concluída"
STATUS_RUNNING = "Em execução"
STATUS_NEXT = "Próxima"
STATUS_UPCOMING = "Futura"

COLOR_PAST = "#c8f7c5"      # verde claro
COLOR_RUNNING = "#58d68d"   # verde forte
COLOR_NEXT = "#f9e79f"      # amarelo suave
COLOR_FUTURE = "#ecf0f1"    # cinza claro

# ---------- Helpers ----------
def now_br() -> datetime:
    return datetime.now(TZINFO)

def parse_time_str(s: str) -> time | None:
    """Aceita 'HH:MM:SS' ou 'HH:MM'. Retorna time ou None se inválido."""
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None

def normalize_hhmmss(t: time | None) -> str:
    return t.strftime("%H:%M:%S") if t else ""

def classify_rows(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    status = []
    for _, r in df.iterrows():
        if r["End"] <= now:
            status.append(STATUS_DONE)
        elif r["Start"] <= now < r["End"]:
            status.append(STATUS_RUNNING)
        else:
            status.append(STATUS_UPCOMING)
    df["Status"] = status
    # primeira futura vira "Próxima"
    upcoming_idx = df.index[df["Status"] == STATUS_UPCOMING].tolist()
    if upcoming_idx:
        df.loc[upcoming_idx[0], "Status"] = STATUS_NEXT
    return df

def style_table(df: pd.DataFrame) -> str:
    preferred = ["Data", "Início", "Fim", "Atividade", "Duração", "Status"]
    fallback  = ["Start", "End", "Activity", "Status"]
    cols = [c for c in preferred if c in df.columns] or [c for c in fallback if c in df.columns]
    view = df[cols].copy()

    def row_style(row):
        val = row.get("Status", "")
        if val == STATUS_RUNNING:
            return [f"background-color: {COLOR_RUNNING}; color: #0b5345;"] * len(row)
        if val == STATUS_DONE:
            return [f"background-color: {COLOR_PAST}; color: #1b4f72;"] * len(row)
        if val == STATUS_NEXT:
            return [f"background-color: {COLOR_NEXT}; color: #7d6608;"] * len(row)
        return [f"background-color: {COLOR_FUTURE}; color: #2c3e50;"] * len(row)

    styler = (
        view.style
        .apply(row_style, axis=1)
        .hide(axis="index")
        .set_table_styles([
            {"selector": "table", "props": [
                ("border-collapse","separate"),("border-spacing","0"),("width","100%"),
                ("font-family","Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial")
            ]},
            {"selector": "th", "props": [
                ("background","#111827"),("color","white"),("position","sticky"),
                ("top","0"),("z-index","1"),("padding","10px 8px"),("text-align","left")
            ]},
            {"selector": "td", "props": [("padding","10px 8px"),("border-bottom","1px solid #e5e7eb")]},
        ])
        .set_properties(**{"font-size":"0.95rem"})
    )
    return styler.to_html()

def ensure_state():
    if "tasks" not in st.session_state:
        st.session_state.tasks = []  # {Date, Start, End, Activity, DurationSeconds?}

def to_df(tasks):
    if not tasks:
        return pd.DataFrame(columns=["Date","Start","End","Activity","DurationSeconds"])
    df = pd.DataFrame(tasks)
    if "DurationSeconds" not in df.columns:
        df["DurationSeconds"] = None
    return df

def human_td(td: timedelta) -> str:
    sign = "-" if td.total_seconds() < 0 else ""
    td = abs(td)
    h, rem = divmod(int(td.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{sign}{h:02d}:{m:02d}:{s:02d}"
    return f"{sign}{m:02d}:{s:02d}"

# ---------- App ----------
ensure_state()

st.title("🗓️ Cronograma de Pista — BTZ Motorsport")
st.caption("Auto-refresh 1s • Fuso fixo Brasília • Campos de Início/Fim com segundos (HH:MM:SS).")

# Sidebar minimal: salvar/carregar
with st.sidebar:
    st.header("💾 Salvar / Carregar")
    df_csv = to_df(st.session_state.tasks)
    if not df_csv.empty:
        st.download_button(
            "⬇️ Baixar CSV",
            data=df_csv.to_csv(index=False).encode("utf-8"),
            file_name="cronograma.csv",
            mime="text/csv",
            use_container_width=True,
        )
    uploaded = st.file_uploader("Carregar CSV", type=["csv"], help="Colunas: Date,Start,End,Activity,DurationSeconds")
    if uploaded is not None:
        up = pd.read_csv(uploaded)
        for c in ["Date","Start","End","Activity","DurationSeconds"]:
            if c not in up.columns:
                up[c] = None
        st.session_state.tasks = [
            {
                "Date": str(r["Date"]) if pd.notna(r["Date"]) else "",
                "Start": str(r["Start"]) if pd.notna(r["Start"]) else "",
                "End": str(r["End"]) if pd.notna(r["End"]) else "",
                "Activity": str(r["Activity"]) if pd.notna(r["Activity"]) else "",
                "DurationSeconds": int(r["DurationSeconds"]) if pd.notna(r["DurationSeconds"]) else None,
            }
            for _, r in up.iterrows()
        ]
        st.success("Cronograma carregado.")

# Auto-refresh 1s (JS) — funciona local e no Cloud
st.markdown("""
<script>setTimeout(function(){window.location.reload();},1000);</script>
""", unsafe_allow_html=True)

# Formulário (Início/Fim com segundos digitáveis)
with st.container():
    st.subheader("➕ Nova atividade")
    c1, c2, c3, c4, c5 = st.columns([1,1.3,1.6,3,1.2])
    with c1:
        d = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
    with c2:
        t_start_str = st.text_input("Início (HH:MM:SS)", value="08:00:00", placeholder="HH:MM:SS")
    with c3:
        t_end_str = st.text_input("Fim (opcional) (HH:MM:SS)", value="09:00:00", placeholder="HH:MM:SS")
    with c4:
        activity = st.text_input("Atividade", placeholder="Briefing / Warmup / Box / etc.")
    with c5:
        dur_secs = st.number_input("Duração (segundos) (opcional)", min_value=0, step=10, value=0)

    c_add = st.columns([1,5])[0]
    with c_add:
        add = st.button("Adicionar", type="primary", use_container_width=True)

    if add:
        if not activity.strip():
            st.error("Informe a atividade.")
        else:
            t_start = parse_time_str(t_start_str)
            if t_start is None:
                st.error("Formato inválido em **Início**. Use HH:MM:SS (ex.: 17:03:25).")
                st.stop()

            # calcula End a partir da duração se fornecida; senão usa campo Fim
            if dur_secs and dur_secs > 0:
                end_dt = datetime.combine(d, t_start).replace(tzinfo=TZINFO) + timedelta(seconds=int(dur_secs))
                end_str = end_dt.strftime("%H:%M:%S")
            else:
                t_end = parse_time_str(t_end_str)
                if t_end is None:
                    st.error("Informe **Fim** no formato HH:MM:SS ou preencha a **Duração (segundos)**.")
                    st.stop()
                if (datetime.combine(d, t_end) <= datetime.combine(d, t_start)):
                    st.error("**Fim** deve ser após **Início** (ou use a duração).")
                    st.stop()
                end_str = t_end.strftime("%H:%M:%S")

            st.session_state.tasks.append({
                "Date": d.isoformat(),
                "Start": t_start.strftime("%H:%M:%S"),
                "End": end_str,
                "Activity": activity.strip(),
                "DurationSeconds": int(dur_secs) if dur_secs and dur_secs > 0 else None,
            })
            st.success("Atividade adicionada.")

# Montagem e visualização
raw = to_df(st.session_state.tasks)

if raw.empty:
    st.info("Nenhuma atividade cadastrada ainda. Use o formulário acima para começar.")
else:
    df = raw.copy()

    # Constrói Start/End como datetime em Brasília (aceita HH:MM ou HH:MM:SS)
    start_str = df["Date"].fillna("").astype(str) + " " + df["Start"].fillna("").astype(str)
    end_str   = df["Date"].fillna("").astype(str) + " " + df["End"].fillna("").astype(str)

    df["Start"] = pd.to_datetime(start_str, errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward", ambiguous="NaT")
    df["End"]   = pd.to_datetime(end_str,   errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward", ambiguous="NaT")

    # Quando existir DurationSeconds, recalcula End = Start + duração
    mask = df["DurationSeconds"].notna() & df["Start"].notna()
    if mask.any():
        df.loc[mask, "End"] = df.loc[mask, "Start"] + df.loc[mask, "DurationSeconds"].astype(int).apply(lambda s: timedelta(seconds=s))

    # Colunas de exibição (com segundos)
    df["Data"]   = df["Start"].dt.strftime("%d/%m/%Y")
    df["Início"] = df["Start"].dt.strftime("%H:%M:%S")
    df["Fim"]    = df["End"].dt.strftime("%H:%M:%S")
    df["Duração"] = (df["End"] - df["Start"]).apply(lambda x: human_td(x) if pd.notna(x) else "—")

    # Limpa inválidos e ordena
    df = df.dropna(subset=["Start","End"]).sort_values(["Start","End"]).reset_index(drop=True)

    # Status e métricas
    now = now_br()
    df = classify_rows(df, now)

    running = df[df["Status"] == STATUS_RUNNING]
    next_up = df[df["Status"] == STATUS_NEXT]
    current_row = running.iloc[0] if not running.empty else None
    next_row = next_up.iloc[0] if not next_up.empty else None

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Agora (Brasília)", now.strftime("%d/%m %H:%M:%S"))
    with k2:
        st.metric("⏱️ Tempo p/ acabar", human_td(current_row["End"] - now) if current_row is not None else "—")
    with k3:
        st.metric("🕒 Tempo p/ próxima", human_td(next_row["Start"] - now) if next_row is not None else "—")
    with k4:
        st.metric("Atividades concluídas", f"{int((df['Status']==STATUS_DONE).sum())}/{len(df)}")

    if current_row is not None:
        total_secs = (current_row["End"] - current_row["Start"]).total_seconds()
        elapsed = (now - current_row["Start"]).total_seconds()
        pct = max(0.0, min(1.0, elapsed / total_secs)) if total_secs > 0 else 0.0
        st.progress(pct, text=f"Em execução: {current_row['Activity']} ({int(pct*100)}%)")

    # Tabela
    st.markdown(style_table(df), unsafe_allow_html=True)

    with st.expander("Legenda de cores"):
        leg = pd.DataFrame({
            "Status": [STATUS_RUNNING, STATUS_DONE, STATUS_NEXT, STATUS_UPCOMING],
            "Cor": [COLOR_RUNNING, COLOR_PAST, COLOR_NEXT, COLOR_FUTURE]
        })
        st.dataframe(leg, hide_index=True, use_container_width=True)

    # Ações
    st.divider()
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        if st.button("🧹 Limpar tudo", type="secondary"):
            st.session_state.tasks = []
            st.experimental_rerun()
    with c2:
        if st.button("🗑️ Remover última"):
            if st.session_state.tasks:
                st.session_state.tasks.pop()
                st.experimental_rerun()
    with c3:
        st.caption("Auto-refresh 1s | Fuso fixo: América/São_Paulo | Início/Fim aceitam HH:MM:SS.")

# Footer
st.write("")
st.markdown("<div style='text-align:center;color:#94a3b8'>Feito com ❤️ para operações de pista BTZ | Streamlit</div>", unsafe_allow_html=True)
