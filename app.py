# app.py
# BTZ Cronograma — atualização 1s, fuso fixo Brasília,
# criação/edição em expanders, TABELA em painel rolável (header visível),
# coluna "Atividade" após "Duração".
# ENCADEAMENTO: atividades encadeadas com GAP fixo de 1 minuto.
# Compatibilidade: aceita dados antigos sem DurationSec (calcula a partir de Start/End).

from __future__ import annotations
import time
from datetime import datetime, date, time as dtime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np
import streamlit as st

# ---------------- Config ----------------
st.set_page_config(page_title="BTZ | Cronograma de Pista", page_icon="🗓️", layout="wide")
TZINFO = ZoneInfo("America/Sao_Paulo")   # sempre Brasília
GAP = timedelta(minutes=1)               # GAP FIXO entre atividades encadeadas

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

def parse_duration_hms(s: str) -> timedelta | None:
    """Aceita 'HH:MM:SS' ou 'MM:SS' -> timedelta."""
    s = (s or "").strip()
    try:
        parts = [int(p) for p in s.split(":")]
        if len(parts) == 2:
            m, s = parts
            if m < 0 or not (0 <= s < 60): return None
            return timedelta(minutes=m, seconds=s)
        elif len(parts) == 3:
            h, m, s = parts
            if h < 0 or m < 0 or not (0 <= s < 60): return None
            return timedelta(hours=h, minutes=m, seconds=s)
        return None
    except Exception:
        return None

def duration_to_hms(td: timedelta) -> str:
    total = max(0, int(td.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

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
    cols = [c for c in preferred if c in df.columns]
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
    # Armazenamos: Date (iso), Start (HH:MM:SS), DurationSec (int), Activity (str)
    if "tasks" not in st.session_state:
        st.session_state.tasks = []

def _safe_int(x, default=0):
    try:
        if pd.isna(x): return default
        return int(x)
    except Exception:
        return default

def normalize_tasks(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Garante as colunas: Date, Start, DurationSec, Activity.
    Se DurationSec faltar, tenta calcular por Start/End (mesmo dataset antigo).
    """
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(columns=["Date","Start","DurationSec","Activity"])

    out = df_raw.copy()

    # Garantir colunas básicas
    for c in ["Date","Start","Activity"]:
        if c not in out.columns:
            out[c] = ""

    # Se não existir DurationSec, tenta derivar de End (versões antigas)
    if "DurationSec" not in out.columns or out["DurationSec"].isna().all():
        if "End" in out.columns:
            # usa a mesma data para computar delta
            try:
                start_dt = pd.to_datetime(out["Date"].astype(str) + " " + out["Start"].astype(str), errors="coerce")
                end_dt   = pd.to_datetime(out["Date"].astype(str) + " " + out["End"].astype(str), errors="coerce")
                dur = (end_dt - start_dt).dt.total_seconds().fillna(0).astype(int).clip(lower=0)
                out["DurationSec"] = dur
            except Exception:
                out["DurationSec"] = 0
        else:
            out["DurationSec"] = 0
    else:
        out["DurationSec"] = out["DurationSec"].apply(_safe_int)

    # Linha a prova de tipos
    out["Date"] = out["Date"].astype(str)
    out["Start"] = out["Start"].astype(str)
    out["Activity"] = out["Activity"].astype(str)

    return out[["Date","Start","DurationSec","Activity"]]

def compute_schedule(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Monta Start/End reais (com TZ) e aplica encadeamento com GAP dentro de cada data."""
    base = normalize_tasks(df_raw)
    if base.empty:
        return pd.DataFrame(columns=["Date","Start","End","DurationSec","Activity"])

    base["Date"] = pd.to_datetime(base["Date"], errors="coerce").dt.date
    base["Start_dt"] = pd.to_datetime(base["Date"].astype(str) + " " + base["Start"].astype(str), errors="coerce").dt.tz_localize(TZINFO, nonexistent="shift_forward")

    # Ordena por data e início
    base = base.dropna(subset=["Date","Start_dt"]).sort_values(["Date","Start_dt"]).reset_index(drop=True)

    # Aplica encadeamento por dia
    prev_end_by_day: dict[date, datetime] = {}
    starts, ends = [], []
    for _, row in base.iterrows():
        d = row["Date"]
        st_dt: datetime = row["Start_dt"]
        dur = timedelta(seconds=_safe_int(row["DurationSec"], 0))
        if d in prev_end_by_day:
            st_dt = prev_end_by_day[d] + GAP
        en_dt = st_dt + dur
        prev_end_by_day[d] = en_dt
        starts.append(st_dt); ends.append(en_dt)

    base["Start"] = starts
    base["End"] = ends
    return base[["Date","Start","End","DurationSec","Activity"]]

# ---------------- Estado ----------------
ensure_state()

# ---------------- Topo ----------------
st.title("🗓️ Cronograma de Pista — BTZ Motorsport")
st.caption("Tabela em painel rolável • Atualização 1s • Fuso Brasília • Encadeamento com GAP de 1 min • Compatível com dados antigos.")

# ---- Nova atividade (expander) -> FIM calculado pela duração ----
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
            dur = parse_duration_hms(dur_str)  # aceita MM:SS
            if t_start is None:
                st.error("Use o formato HH:MM:SS em **Início**.")
            elif dur is None:
                st.error("Use o formato MM:SS em **Duração** (ex.: 05:30).")
            else:
                st.session_state.tasks.append({
                    "Date": d.isoformat(),
                    "Start": t_start.strftime("%H:%M:%S"),
                    "DurationSec": int(dur.total_seconds()),
                    "Activity": activity.strip(),
                })
                st.success("Atividade adicionada.")
                st.rerun()

# ---- Editar atividades (expander) ----
with st.expander("»»", expanded=False):
    if not st.session_state.tasks:
        st.info("Nenhuma atividade para editar ainda.")
    else:
        raw = normalize_tasks(pd.DataFrame(st.session_state.tasks)).reset_index().rename(columns={"index":"ID"})
        raw["Duration"] = raw["DurationSec"].apply(lambda s: duration_to_hms(timedelta(seconds=int(s))))

        edited = st.data_editor(
            raw[["ID","Date","Start","Duration","Activity"]],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "ID": st.column_config.NumberColumn(disabled=True),
                "Date": st.column_config.TextColumn(help="YYYY-MM-DD"),
                "Start": st.column_config.TextColumn(help="HH:MM:SS"),
                "Duration": st.column_config.TextColumn(help="Edite em HH:MM:SS (ou MM:SS)"),
                "Activity": st.column_config.TextColumn(help="Descrição da atividade"),
            },
            key="editor_linked",
        )

        colA, colB, colC = st.columns([1,1,2])
        with colA:
            do_save = st.button("💾 Salvar & Reencadear", type="primary", use_container_width=True)
        with colB:
            to_delete = st.number_input("ID para remover", min_value=0, step=1, value=0,
                                        help="Informe o ID da linha para excluir.")
            do_delete = st.button("🗑️ Remover ID", use_container_width=True)

        if do_delete:
            if to_delete in edited["ID"].values:
                edited = edited[edited["ID"] != to_delete].reset_index(drop=True)
                st.success(f"Removido ID {to_delete}. Clique em **Salvar & Reencadear** para confirmar.")
            else:
                st.warning("ID não encontrado na tabela acima.")

        if do_save:
            new_tasks: list[dict] = []
            errors: list[str] = []
            for i, r in edited.iterrows():
                date_str = str(r.get("Date","")).strip()
                start_str = str(r.get("Start","")).strip()
                dur_str   = str(r.get("Duration","")).strip()
                act       = str(r.get("Activity","")).strip()

                if not (date_str and start_str and dur_str and act):
                    errors.append(f"Linha {i}: campos vazios."); continue
                try:
                    d_parsed = datetime.fromisoformat(date_str).date()
                except ValueError:
                    errors.append(f"Linha {i}: Date inválida (use YYYY-MM-DD)."); continue
                t_start = parse_time_str(start_str)
                if t_start is None:
                    errors.append(f"Linha {i}: Início inválido (use HH:MM:SS)."); continue
                dur = parse_duration_hms(dur_str)
                if dur is None:
                    errors.append(f"Linha {i}: Duração inválida (use HH:MM:SS ou MM:SS)."); continue

                new_tasks.append({
                    "Date": d_parsed.isoformat(),
                    "Start": t_start.strftime("%H:%M:%S"),
                    "DurationSec": int(dur.total_seconds()),
                    "Activity": act,
                })

            if errors:
                st.error("Não foi possível salvar por causa de erros:\n- " + "\n- ".join(errors))
            else:
                st.session_state.tasks = new_tasks
                st.success("Alterações salvas e atividades reencadeadas.")
                st.rerun()

# ---- KPIs + barra ----
if st.session_state.tasks:
    base_df = normalize_tasks(pd.DataFrame(st.session_state.tasks))
    sched = compute_schedule(base_df)

    now = now_br()
    view = sched.copy()
    view["Data"]      = view["Start"].dt.strftime("%d/%m/%Y")
    view["Início"]    = view["Start"].dt.strftime("%H:%M:%S")
    view["Fim"]       = view["End"].dt.strftime("%H:%M:%S")
    view["Duração"]   = view["DurationSec"].apply(lambda s: duration_to_hms(timedelta(seconds=int(s))))
    view = classify_rows(view, now)

    running = view[view["Status"] == STATUS_RUNNING]
    next_up = view[view["Status"] == STATUS_NEXT]
    current_row = running.iloc[0] if not running.empty else None
    next_row = next_up.iloc[0] if not next_up.empty else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Agora (Brasília)", now.strftime("%d/%m %H:%M:%S"))
    k2.metric("⏱️ Tempo p/ acabar", human_td(current_row["End"] - now) if current_row is not None else "—")
    k3.metric("🕒 Tempo p/ próxima", human_td(next_row["Start"] - now) if next_row is not None else "—")
    k4.metric("Atividades concluídas", f"{int((view['Status']==STATUS_DONE).sum())}/{len(view)}")

    if current_row is not None:
        total_secs = (current_row["End"] - current_row["Start"]).total_seconds()
        elapsed = (now - current_row["Start"]).total_seconds()
        pct = max(0.0, min(1.0, elapsed / total_secs)) if total_secs > 0 else 0.0
        st.progress(pct, text=f"Em execução: {current_row['Activity']} ({int(pct*100)}%)")

# ---- Tabela (painel rolável) ----
if not st.session_state.tasks:
    st.info("Sem atividades cadastradas.")
else:
    base_df = normalize_tasks(pd.DataFrame(st.session_state.tasks))
    sched = compute_schedule(base_df)
    sched["Data"]      = sched["Start"].dt.strftime("%d/%m/%Y")
    sched["Início"]    = sched["Start"].dt.strftime("%H:%M:%S")
    sched["Fim"]       = sched["End"].dt.strftime("%H:%M:%S")
    sched["Duração"]   = sched["DurationSec"].apply(lambda s: duration_to_hms(timedelta(seconds=int(s))))
    sched = classify_rows(sched, now_br())

    html_table = style_table(sched)
    st.markdown(f'<div class="btz-table-panel">{html_table}</div>', unsafe_allow_html=True)

# ---- Auto-refresh 1s ----
time.sleep(1.0)
st.rerun()
