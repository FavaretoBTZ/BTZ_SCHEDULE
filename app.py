# app.py
# BTZ Cronograma — atualização 1s, fuso fixo Brasília,
# criação/edição em expanders, TABELA em painel rolável (header visível),
# coluna "Atividade" após "Duração".
# >> "Nova atividade": usa Início (HH:MM:SS) + Duração (MM:SS) e calcula Fim automaticamente.

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

# --------- CSS/JS: painel rolável da tabela + preservação do scroll ---------
st.markdown("""
<style>
.btz-table-panel {
  max-height: 65vh;
  overflow-y: auto;
  padding-right: 6px;
  border: 1px solid #1f2937;
  border-radius: 10px;
  background: #0b0f19;
}
.btz-table-panel table thead th { position: sticky; top: 0; z-index: 2; }
.stProgress > div > div { height: 10px; }
</style>
<script>
(function(){
  const KEY="btz_scrollY";
  const restore=()=>{const y=sessionStorage.getItem(KEY); if(y!==null) window.scrollTo(0, parseFloat(y));};
  const save=()=>sessionStorage.setItem(KEY, window.scrollY);
  setInterval(save, 300); restore();
})();
</script>
""", unsafe_allow_html=True)

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

def parse_duration_mmss(s: str) -> timedelta | None:
    """Converte 'MM:SS' em timedelta."""
    s = (s or "").strip()
    try:
        parts = s.split(":")
        if len(parts) != 2: return None
        m = int(parts[0]); s = int(parts[1])
        if m < 0 or s < 0 or s >= 60: return None
        return timedelta(minutes=m, seconds=s)
    except Exception:
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
    preferred = ["Data","Início","Fim","Duração","Atividade","Status"]
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
                        {"selector":"th","props":[("background","#111827"),("color","white"),("position","sticky"),
                                                  ("top","0"),("z-index","2"),("padding","10px 8px"),("text-align","left")]},
                        {"selector":"td","props":[("padding","10px 8px"),("border-bottom","1px solid #e5e7eb")]}
                    ])
                    .set_properties(**{"font-size":"0.95rem"}))
    return styler.to_html()

def ensure_state():
    if "tasks" not in st.session_state:
        st.session_state.tasks = []  # {Date, Start, End, Activity}

# ---------------- Estado ----------------
ensure_state()

# ---------------- Topo ----------------
st.title("🗓️ Cronograma de Pista — BTZ Motorsport")
st.caption("Header fixo da página • Atualização 1s • Fuso Brasília • **Nova atividade: Início (HH:MM:SS) + Duração (MM:SS)**.")

# ---- Nova atividade (expander) -> FIM calculado automaticamente ----
with st.expander("»»", expanded=False):
    c1, c2, c3 = st.columns([1,1.5,3.5])
    with c1:
        d = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
    with c2:
        t_start_str = st.text_input("Início (HH:MM:SS)", value="08:00:00", placeholder="HH:MM:SS")
    with c3:
        dur_str = st.text_input("Duração (MM:SS)", value="00:45", placeholder="MM:SS")
    activity = st.text_input("Atividade", placeholder="Briefing / Warmup / Box / etc.", key="new_activity")

    if st.button("Adicionar", type="primary"):
        if not activity.strip():
            st.error("Informe a atividade.")
        else:
            t_start = parse_time_str(t_start_str)
            dur = parse_duration_mmss(dur_str)
            if t_start is None:
                st.error("Use o formato HH:MM:SS em **Início**.")
            elif dur is None:
                st.error("Use o formato MM:SS em **Duração** (ex.: 05:30).")
            else:
                start_dt = datetime.combine(d, t_start).replace(tzinfo=TZINFO)
                end_dt = start_dt + dur
                st.session_state.tasks.append({
                    "Date": d.isoformat(),
                    "Start": t_start.strftime("%H:%M:%S"),
                    "End":   end_dt.strftime("%H:%M:%S"),  # armazenamos somente hora local
                    "Activity": activity.strip(),
                })
                st.success(f"Atividade adicionada. Fim calculado: {end_dt.strftime('%H:%M:%S')}")
                st.rerun()

# ---- Editar atividades (expander) ----
with st.expander("»»", expanded=False):
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
            to_delete = st.number_input("ID para remover", min_value=0, step=1, value=0,
                                        help="Informe o ID da linha para excluir.")
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
                    errors.append(f"Linha {i}: campos vazios."); continue
                try:
                    d_parsed = datetime.fromisoformat(date_str).date()
                except ValueError:
                    errors.append(f"Linha {i}: Date inválida (use YYYY-MM-DD)."); continue
                t_start = parse_time_str(start_str)
                t_end   = parse_time_str(end_str)
                if t_start is None or t_end is None:
                    errors.append(f"Linha {i}: horários inválidos (use HH:MM:SS)."); continue
                if datetime.combine(d_parsed, t_end) <= datetime.combine(d_parsed, t_start):
                    errors.append(f"Linha {i}: Fim deve ser após Início."); continue
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

# ---- KPIs + barra ----
if st.session_state.tasks:
    df_tmp = pd.DataFrame(st.session_state.tasks)
    start_str = df_tmp["Date"].astype(str) + " " + df_tmp["Start"].astype(str)
    end_str   = df_tmp["Date"].astype(str) + " " + df_tmp["End"].astype(str)
    df_tmp["Start"] = pd.to_datetime(start_str, errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward", ambiguous="NaT")
    df_tmp["End"]   = pd.to_datetime(end_str,   errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward", ambiguous="NaT")
    df_tmp = df_tmp.dropna(subset=["Start","End"]).sort_values(["Start","End"]).reset_index(drop=True)

    now = now_br()
    df_view = df_tmp.copy()
    df_view["Data"]      = df_view["Start"].dt.strftime("%d/%m/%Y")
    df_view["Início"]    = df_view["Start"].dt.strftime("%H:%M:%S")
    df_view["Fim"]       = df_view["End"].dt.strftime("%H:%M:%S")
    df_view["Duração"]   = (df_view["End"] - df_view["Start"]).apply(lambda x: human_td(x))
    df_view["Atividade"] = df_view.get("Activity", df_view.get("Atividade", pd.Series([""]*len(df_view))))
    df_view = classify_rows(df_view, now)

    running = df_view[df_view["Status"] == STATUS_RUNNING]
    next_up = df_view[df_view["Status"] == STATUS_NEXT]
    current_row = running.iloc[0] if not running.empty else None
    next_row = next_up.iloc[0] if not next_up.empty else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Agora (Brasília)", now.strftime("%d/%m %H:%M:%S"))
    k2.metric("⏱️ Tempo p/ acabar", human_td(current_row["End"] - now) if current_row is not None else "—")
    k3.metric("🕒 Tempo p/ próxima", human_td(next_row["Start"] - now) if next_row is not None else "—")
    k4.metric("Atividades concluídas", f"{int((df_view['Status']==STATUS_DONE).sum())}/{len(df_view)}")

    if current_row is not None:
        total_secs = (current_row["End"] - current_row["Start"]).total_seconds()
        elapsed = (now - current_row["Start"]).total_seconds()
        pct = max(0.0, min(1.0, elapsed / total_secs)) if total_secs > 0 else 0.0
        st.progress(pct, text=f"Em execução: {current_row['Activity']} ({int(pct*100)}%)")

# ---- Tabela (painel rolável) ----
if not st.session_state.tasks:
    st.info("Sem atividades cadastradas.")
else:
    df = pd.DataFrame(st.session_state.tasks)
    start_str = df["Date"].astype(str) + " " + df["Start"].astype(str)
    end_str   = df["Date"].astype(str) + " " + df["End"].astype(str)
    df["Start"] = pd.to_datetime(start_str, errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward", ambiguous="NaT")
    df["End"]   = pd.to_datetime(end_str,   errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward", ambiguous="NaT")

    df["Data"]      = df["Start"].dt.strftime("%d/%m/%Y")
    df["Início"]    = df["Start"].dt.strftime("%H:%M:%S")
    df["Fim"]       = df["End"].dt.strftime("%H:%M:%S")
    df["Duração"]   = (df["End"] - df["Start"]).apply(lambda x: human_td(x))
    df["Atividade"] = df.get("Activity", df.get("Atividade", pd.Series([""]*len(df))))
    df = df.dropna(subset=["Start","End"]).sort_values(["Start","End"]).reset_index(drop=True)
    df = classify_rows(df, now_br())

    html_table = style_table(df)
    st.markdown(f'<div class="btz-table-panel">{html_table}</div>', unsafe_allow_html=True)

# ---- Auto-refresh 1s ----
time.sleep(1.0)
st.rerun()
