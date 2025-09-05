# app.py
# BTZ Cronograma — atualização 1s (status + contadores), fuso fixo Brasília,
# Início/Fim com HH:MM:SS e edição de atividades (SEM "Legenda de cores").

from __future__ import annotations
import time
from datetime import datetime, date, time as dtime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# ---------------- Config ----------------
st.set_page_config(page_title="BTZ | Cronograma de Pista", page_icon="🗓️", layout="wide")

TZINFO = ZoneInfo("America/Sao_Paulo")  # sempre Brasília

STATUS_DONE = "Concluída"
STATUS_RUNNING = "Em execução"
STATUS_NEXT = "Próxima"
STATUS_UPCOMING = "Futura"

COLOR_PAST = "#c8f7c5"
COLOR_RUNNING = "#58d68d"
COLOR_NEXT = "#f9e79f"
COLOR_FUTURE = "#ecf0f1"

# ---------------- Helpers ----------------
def now_br() -> datetime:
    return datetime.now(TZINFO)

def parse_time_str(s: str) -> dtime | None:
    s = (s or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    return None

def human_td(td: timedelta) -> str:
    sign = "-" if td.total_seconds() < 0 else ""
    td = abs(td)
    h, rem = divmod(int(td.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{h:02d}:{m:02d}:{s:02d}" if h else f"{sign}{m:02d}:{s:02d}"

def classify_rows(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    def _stat(r):
        if r.End <= now: return STATUS_DONE
        if r.Start <= now < r.End: return STATUS_RUNNING
        return STATUS_UPCOMING
    df["Status"] = df.apply(_stat, axis=1)
    fut = df.index[df["Status"] == STATUS_UPCOMING].tolist()
    if fut:
        df.loc[fut[0], "Status"] = STATUS_NEXT
    return df

def style_table(df: pd.DataFrame) -> str:
    preferred = ["Data","Início","Fim","Atividade","Duração","Status"]
    fallback  = ["Start","End","Activity","Status"]
    cols = [c for c in preferred if c in df.columns] or [c for c in fallback if c in df.columns]
    view = df[cols].copy()

    def row_style(row):
        val = row.get("Status", "")
        if val == STATUS_RUNNING: return [f"background-color:{COLOR_RUNNING}; color:#0b5345;"]*len(row)
        if val == STATUS_DONE:    return [f"background-color:{COLOR_PAST}; color:#1b4f72;"]*len(row)
        if val == STATUS_NEXT:    return [f"background-color:{COLOR_NEXT}; color:#7d6608;"]*len(row)
        return [f"background-color:{COLOR_FUTURE}; color:#2c3e50;"]*len(row)

    styler = (view.style.apply(row_style, axis=1)
                    .hide(axis="index")
                    .set_table_styles([
                        {"selector":"table","props":[("border-collapse","separate"),("border-spacing","0"),("width","100%"),("font-family","Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial")]},
                        {"selector":"th","props":[("background","#111827"),("color","white"),("position","sticky"),("top","0"),("z-index","1"),("padding","10px 8px"),("text-align","left")]},
                        {"selector":"td","props":[("padding","10px 8px"),("border-bottom","1px solid #e5e7eb")]}
                    ])
                    .set_properties(**{"font-size":"0.95rem"}))
    return styler.to_html()

def ensure_state():
    if "tasks" not in st.session_state:
        st.session_state.tasks = []  # {Date, Start, End, Activity}
    if "pause_refresh" not in st.session_state:
        st.session_state.pause_refresh = False

# ---------------- Estado ----------------
ensure_state()

st.title("🗓️ Cronograma de Pista — BTZ Motorsport")
st.caption("Atualização automática de 1s (status + contadores) • Fuso fixo Brasília • Início/Fim com HH:MM:SS • Edição de atividades.")

# --------- Sidebar (Salvar/Carregar & Edição) ---------
with st.sidebar:
    st.header("💾 Salvar / Carregar")
    df_csv = pd.DataFrame(st.session_state.tasks) if st.session_state.tasks else pd.DataFrame(
        columns=["Date","Start","End","Activity"]
    )
    st.download_button("⬇️ Baixar CSV", df_csv.to_csv(index=False).encode("utf-8"),
                       "cronograma.csv", "text/csv", use_container_width=True)
    up = st.file_uploader("Carregar CSV", type=["csv"])
    if up is not None:
        df_up = pd.read_csv(up)
        for c in ["Date","Start","End","Activity"]:
            if c not in df_up.columns: df_up[c] = None
        st.session_state.tasks = [
            {"Date": str(r["Date"]) if pd.notna(r["Date"]) else "",
             "Start": str(r["Start"]) if pd.notna(r["Start"]) else "",
             "End": str(r["End"]) if pd.notna(r["End"]) else "",
             "Activity": str(r["Activity"]) if pd.notna(r["Activity"]) else ""}
            for _, r in df_up.iterrows()
        ]
        st.success("Cronograma carregado.")

    st.divider()
    st.subheader("✏️ Modo edição")
    st.session_state.pause_refresh = st.toggle(
        "Pausar atualização automática enquanto edito",
        value=False,
        help="Ative para editar sem a página atualizar a cada 1s."
    )

# ------------- Formulário (criar nova) -------------
st.subheader("➕ Nova atividade")
c1, c2, c3, c4 = st.columns([1,1.5,1.7,3.8])
with c1:
    d = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
with c2:
    t_start_str = st.text_input("Início (HH:MM:SS)", value="08:00:00", placeholder="HH:MM:SS")
with c3:
    t_end_str = st.text_input("Fim (HH:MM:SS)", value="09:00:00", placeholder="HH:MM:SS")
with c4:
    activity = st.text_input("Atividade", placeholder="Briefing / Warmup / Box / etc.")

if st.button("Adicionar", type="primary"):
    if not activity.strip():
        st.error("Informe a atividade.")
    else:
        t_start = parse_time_str(t_start_str)
        t_end = parse_time_str(t_end_str)
        if t_start is None or t_end is None:
            st.error("Use o formato HH:MM:SS em **Início** e **Fim**.")
        elif datetime.combine(d, t_end) <= datetime.combine(d, t_start):
            st.error("**Fim** deve ser após **Início**.")
        else:
            st.session_state.tasks.append({
                "Date": d.isoformat(),
                "Start": t_start.strftime("%H:%M:%S"),
                "End": t_end.strftime("%H:%M:%S"),
                "Activity": activity.strip(),
            })
            st.success("Atividade adicionada.")

# ------------- Edição de atividades -------------
st.subheader("🛠️ Editar atividades existentes")

if not st.session_state.tasks:
    st.info("Nenhuma atividade para editar ainda.")
else:
    raw_df = pd.DataFrame(st.session_state.tasks).reset_index().rename(columns={"index":"ID"})
    edited_df = st.data_editor(
        raw_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "ID": st.column_config.NumberColumn(disabled=True),
            "Date": st.column_config.TextColumn(help="YYYY-MM-DD"),
            "Start": st.column_config.TextColumn(help="HH:MM:SS"),
            "End": st.column_config.TextColumn(help="HH:MM:SS"),
            "Activity": st.column_config.TextColumn(help="Descrição da atividade"),
        },
        key="editor",
    )

    colA, colB, colC = st.columns([1,1,2])
    with colA:
        do_save = st.button("💾 Salvar alterações", type="primary", use_container_width=True)
    with colB:
        to_delete = st.number_input("ID para remover", min_value=0, step=1, value=0, help="Informe o ID da linha para excluir.")
        do_delete = st.button("🗑️ Remover ID", use_container_width=True)

    if do_delete:
        if to_delete in edited_df["ID"].values:
            edited_df = edited_df[edited_df["ID"] != to_delete].reset_index(drop=True)
            st.success(f"Removido ID {to_delete}. Clique em **Salvar alterações** para confirmar.")
        else:
            st.warning("ID não encontrado na tabela acima.")

    if do_save:
        new_tasks: list[dict] = []
        errors: list[str] = []
        for i, r in edited_df.iterrows():
            date_str = str(r.get("Date","")).strip()
            start_str = str(r.get("Start","")).strip()
            end_str   = str(r.get("End","")).strip()
            act       = str(r.get("Activity","")).strip()

            if not (date_str and start_str and end_str and act):
                errors.append(f"Linha {i}: campos vazios.")
                continue

            try:
                d_parsed = datetime.fromisoformat(date_str).date()
            except ValueError:
                errors.append(f"Linha {i}: Date inválida (use YYYY-MM-DD).")
                continue

            t_start = parse_time_str(start_str)
            t_end   = parse_time_str(end_str)
            if t_start is None or t_end is None:
                errors.append(f"Linha {i}: horários inválidos (use HH:MM:SS).")
                continue

            if datetime.combine(d_parsed, t_end) <= datetime.combine(d_parsed, t_start):
                errors.append(f"Linha {i}: Fim deve ser após Início.")
                continue

            new_tasks.append({
                "Date": d_parsed.isoformat(),
                "Start": t_start.strftime("%H:%M:%S"),
                "End":   t_end.strftime("%H:%M:%S"),
                "Activity": act,
            })

        if errors:
            st.error("Não foi possível salvar por causa de erros:\n- " + "\n- ".join(errors))
        else:
            st.session_state.tasks = new_tasks
            st.success("Alterações salvas.")
            st.rerun()

# ------------- Construção da visão -------------
if not st.session_state.tasks:
    st.stop()
else:
    df = pd.DataFrame(st.session_state.tasks)

    start_str = df["Date"].fillna("").astype(str) + " " + df["Start"].fillna("").astype(str)
    end_str   = df["Date"].fillna("").astype(str) + " " + df["End"].fillna("").astype(str)
    df["Start"] = pd.to_datetime(start_str, errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward", ambiguous="NaT")
    df["End"]   = pd.to_datetime(end_str,   errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward", ambiguous="NaT")

    df["Data"]    = df["Start"].dt.strftime("%d/%m/%Y")
    df["Início"]  = df["Start"].dt.strftime("%H:%M:%S")
    df["Fim"]     = df["End"].dt.strftime("%H:%M:%S")
    df["Duração"] = (df["End"] - df["Start"]).apply(lambda x: human_td(x) if pd.notna(x) else "—")
    df = df.dropna(subset=["Start","End"]).sort_values(["Start","End"]).reset_index(drop=True)

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

    # Progresso da atual
    if current_row is not None:
        total_secs = (current_row["End"] - current_row["Start"]).total_seconds()
        elapsed = (now - current_row["Start"]).total_seconds()
        pct = max(0.0, min(1.0, elapsed / total_secs)) if total_secs > 0 else 0.0
        st.progress(pct, text=f"Em execução: {current_row['Activity']} ({int(pct*100)}%)")

    # Tabela estilizada (SEM legenda de cores)
    st.markdown(style_table(df), unsafe_allow_html=True)

# ---------------- Auto-refresh 1s (pode pausar no modo edição) ----------------
if not st.session_state.pause_refresh:
    time.sleep(1.0)
    st.rerun()
