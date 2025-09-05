# app.py
# Streamlit schedule tracker — clean & visual (versão corrigida)
# Run local:  streamlit run app.py
# Deploy:     suba no GitHub e aponte o Streamlit Cloud para app.py

from __future__ import annotations
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

# ---------- Page setup ----------
st.set_page_config(
    page_title="BTZ | Cronograma de Pista",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Helpers ----------
def now_tz(tz_name: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now()

STATUS_DONE = "Concluída"
STATUS_RUNNING = "Em execução"
STATUS_NEXT = "Próxima"
STATUS_UPCOMING = "Futura"

COLOR_PAST = "#c8f7c5"      # verde claro
COLOR_RUNNING = "#58d68d"   # verde forte
COLOR_NEXT = "#f9e79f"      # amarelo suave
COLOR_FUTURE = "#ecf0f1"    # cinza claro

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

    # Marca a primeira futura como "Próxima"
    upcoming_idx = df.index[df["Status"] == STATUS_UPCOMING].tolist()
    if upcoming_idx:
        df.loc[upcoming_idx[0], "Status"] = STATUS_NEXT
    return df

def style_table(df: pd.DataFrame) -> str:
    """
    Gera tabela estilizada sem dar KeyError se alguma coluna não existir.
    Usa as colunas formatadas se disponíveis; caso contrário, cai no mínimo viável.
    """
    # prioridades de colunas para exibir
    preferred = ["Data", "Início", "Fim", "Atividade", "Duração", "Status"]
    fallback  = ["Start", "End", "Activity", "Status"]

    cols = [c for c in preferred if c in df.columns]
    if not cols:  # se ainda não formatou, usa o mínimo
        cols = [c for c in fallback if c in df.columns]

    view = df[cols].copy()

    def row_style(row):
        if "Status" in row and row["Status"] == STATUS_RUNNING:
            return [f"background-color: {COLOR_RUNNING}; color: #0b5345;"] * len(row)
        if "Status" in row and row["Status"] == STATUS_DONE:
            return [f"background-color: {COLOR_PAST}; color: #1b4f72;"] * len(row)
        if "Status" in row and row["Status"] == STATUS_NEXT:
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
    if "tz" not in st.session_state:
        st.session_state.tz = "America/Sao_Paulo"
    if "tasks" not in st.session_state:
        st.session_state.tasks = []

def to_df(tasks):
    if not tasks:
        return pd.DataFrame(columns=["Date","Start","End","Activity"])
    return pd.DataFrame(tasks)

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
st.caption("Cadastre atividades, veja o status em tempo real e acompanhe o tempo restante da sessão atual e a próxima atividade.")

with st.sidebar:
    st.header("⚙️ Configurações")
    tz = st.selectbox("Fuso horário", ["America/Sao_Paulo","UTC","America/New_York","Europe/Lisbon","Europe/Paris"], index=0, key="tz")
    refresh_sec = st.slider("Atualizar automaticamente (segundos)", 10, 120, 30, step=10)
    auto = st.checkbox("Ativar auto-refresh", value=True, help="Recarrega a página automaticamente para atualizar o relógio.")
    st.divider()
    st.write("💾 **Salvar / Carregar**")
    df_csv = to_df(st.session_state.tasks)
    if not df_csv.empty:
        csv = df_csv.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Baixar CSV", data=csv, file_name="cronograma.csv", mime="text/csv")
    uploaded = st.file_uploader("Carregar CSV", type=["csv"], help="Colunas: Date,Start,End,Activity")
    if uploaded is not None:
        up = pd.read_csv(uploaded)
        tasks = []
        for _, r in up.iterrows():
            tasks.append({"Date": str(r["Date"]), "Start": str(r["Start"]), "End": str(r["End"]), "Activity": str(r["Activity"])})
        st.session_state.tasks = tasks
        st.success("Cronograma carregado.")

# Auto-refresh simples via JS (para Cloud)
if 'js_ref' not in st.session_state:
    st.session_state.js_ref = 0
if auto:
    st.session_state.js_ref += 1
    st.markdown(f"""
    <script>
    setTimeout(function() {{
      window.location.reload();
    }}, {int(refresh_sec)*1000});
    </script>
    """, unsafe_allow_html=True)

# Formulário de inclusão
with st.container():
    st.subheader("➕ Nova atividade")
    c1, c2, c3, c4, c5 = st.columns([1,1,1.2,3,1])
    with c1:
        d = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
    with c2:
        t_start = st.time_input("Início", value=time(8,0))
    with c3:
        t_end = st.time_input("Fim", value=time(9,0))
    with c4:
        activity = st.text_input("Atividade", placeholder="Briefing / Warmup / Box / etc.")
    with c5:
        st.write("") ; st.write("")
        add = st.button("Adicionar", type="primary", use_container_width=True)

    if add:
        if not activity.strip():
            st.error("Informe a atividade.")
        elif t_end <= t_start:
            st.error("O horário de **Fim** deve ser após o **Início**.")
        else:
            st.session_state.tasks.append({
                "Date": d.isoformat(),
                "Start": time.isoformat(t_start, timespec="minutes"),
                "End": time.isoformat(t_end, timespec="minutes"),
                "Activity": activity.strip(),
            })
            st.success("Atividade adicionada.")

# Montagem do DataFrame
raw = to_df(st.session_state.tasks)

if raw.empty:
    st.info("Nenhuma atividade cadastrada ainda. Use o formulário acima para começar.")
else:
    tzinfo = ZoneInfo(st.session_state.tz)

    # Parse p/ datetime
    df = raw.copy()
    df["Start"] = pd.to_datetime(df["Date"] + " " + df["Start"]).dt.tz_localize(
        tzinfo, nonexistent="shift_forward", ambiguous="NaT"
    )
    df["End"] = pd.to_datetime(df["Date"] + " " + df["End"]).dt.tz_localize(
        tzinfo, nonexistent="shift_forward", ambiguous="NaT"
    )

    # Colunas de exibição
    df["Data"] = df["Start"].dt.strftime("%d/%m/%Y")
    df["Início"] = df["Start"].dt.strftime("%H:%M")
    df["Fim"] = df["End"].dt.strftime("%H:%M")
    df["Duração"] = (df["End"] - df["Start"]).apply(lambda x: human_td(x))

    # Ordena
    df = df.sort_values(["Start", "End"]).reset_index(drop=True)

    # Status
    now = now_tz(st.session_state.tz)
    df = classify_rows(df, now)

    # Atual e próxima
    running = df[df["Status"] == STATUS_RUNNING]
    next_up = df[df["Status"] == STATUS_NEXT]
    current_row = running.iloc[0] if not running.empty else None
    next_row = next_up.iloc[0] if not next_up.empty else None

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Agora", now.strftime("%d/%m %H:%M:%S"))
    with k2:
        if current_row is not None:
            ends_in = current_row["End"] - now
            st.metric("⏱️ Tempo p/ acabar", human_td(ends_in))
        else:
            st.metric("⏱️ Tempo p/ acabar", "—")
    with k3:
        if next_row is not None:
            until_next = next_row["Start"] - now
            st.metric("🕒 Tempo p/ próxima", human_td(until_next))
        else:
            st.metric("🕒 Tempo p/ próxima", "—")
    with k4:
        total = len(df)
        done = int((df["Status"] == STATUS_DONE).sum())
        st.metric("Atividades concluídas", f"{done}/{total}")

    # Barra de progresso da atual
    if current_row is not None:
        total_secs = (current_row["End"] - current_row["Start"]).total_seconds()
        elapsed = (now - current_row["Start"]).total_seconds()
        pct = max(0.0, min(1.0, elapsed / total_secs)) if total_secs > 0 else 0.0
        st.progress(pct, text=f"Em execução: {current_row['Activity']} ({int(pct*100)}%)")

    # Tabela estilizada (AGORA SEM KEYERROR)
    html = style_table(df)
    st.markdown(html, unsafe_allow_html=True)

    # Legenda
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
        st.caption("Dica: mantenha esta página aberta no box; a tabela atualiza automaticamente conforme o relógio do computador (com auto-refresh ativado).")

# Footer
st.write("")
st.markdown("<div style='text-align:center;color:#94a3b8'>Feito com ❤️ para operações de pista BTZ | Streamlit</div>", unsafe_allow_html=True)
