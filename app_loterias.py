import streamlit as st
import requests
import pandas as pd
import numpy as np
from collections import Counter
import plotly.express as px
import random

st.set_page_config(
    page_title="Loterias Caixa",
    page_icon="🍀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .header-caixa {
        background: linear-gradient(90deg, #006B3F, #00A651);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    .numero-btn {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        border: 2px solid #00A651;
        background: white;
        color: #00A651;
        font-weight: bold;
        margin: 4px;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }
    .numero-btn.selected {
        background: #00A651;
        color: white;
    }
    .premio-box {
        background: white;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
    }
    .premio-valor { font-size: 1.8rem; font-weight: 800; color: #00A651; }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="header-caixa">
    <h1 style="margin:0;">🍀 Loterias Caixa</h1>
    <p style="margin:0; opacity:0.9;">Monte seus jogos ou use a formulação inteligente</p>
</div>
""", unsafe_allow_html=True)

st.warning("⚠️ Os sorteios são aleatórios. Análises não aumentam a chance real. Jogue com responsabilidade.")

# Loterias
LOTERIAS = {
    "Mega-Sena": {"json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/mega-sena.json", "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/", "min_num": 1, "max_num": 60, "qtd_numeros": 6, "cor": "#00A651", "dois_sorteios": False},
    "Lotofácil": {"json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotofacil.json", "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/", "min_num": 1, "max_num": 25, "qtd_numeros": 15, "cor": "#9B1B6E", "dois_sorteios": False},
    "Quina": {"json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/quina.json", "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/", "min_num": 1, "max_num": 80, "qtd_numeros": 5, "cor": "#4B0082", "dois_sorteios": False},
    "Dupla Sena": {"json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/dupla-sena.json", "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena/", "min_num": 1, "max_num": 50, "qtd_numeros": 6, "cor": "#C41E3A", "dois_sorteios": True},
}

@st.cache_data(ttl=600)
def buscar_ultimo(url):
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        d = r.json()
        return {
            "concurso": d.get("numero"),
            "data": d.get("dataApuracao"),
            "numeros": [int(x) for x in d.get("listaDezenas", [])],
            "numeros2": [int(x) for x in d.get("listaDezenasSegundoSorteio", []) or []],
            "acumulado": d.get("acumulado", False),
            "proximo": d.get("valorEstimadoProximoConcurso", "N/A"),
            "data_prox": d.get("dataProximoConcurso")
        }
    except:
        return None

@st.cache_data(ttl=3600)
def carregar_hist(url, dois=False):
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        dados = r.json()
        regs = []
        for item in dados:
            if dois:
                n1 = [int(x) for x in item.get("resultado_1", item.get("resultado", []))]
                n2 = [int(x) for x in item.get("resultado_2", [])]
            else:
                n1 = [int(x) for x in item.get("resultado", [])]
                n2 = []
            regs.append({"concurso": item.get("concurso"), "data": item.get("data"), "numeros": n1, "numeros2": n2})
        return pd.DataFrame(regs).sort_values("concurso").reset_index(drop=True)
    except:
        return pd.DataFrame()

def analisar_freq(df, mn, mx):
    todos = [n for nums in df["numeros"] for n in nums]
    c = Counter(todos)
    return pd.DataFrame({"numero": range(mn, mx+1), "freq": [c.get(i,0) for i in range(mn, mx+1)]}).sort_values("freq", ascending=False)

def analisar_atraso(df, mn, mx):
    if df.empty: return pd.DataFrame()
    ult = df["concurso"].max()
    atr = {}
    for n in range(mn, mx+1):
        ap = df[df["numeros"].apply(lambda x: n in x)]
        atr[n] = ult if ap.empty else ult - ap["concurso"].max()
    return pd.DataFrame({"numero": list(atr.keys()), "atraso": list(atr.values())}).sort_values("atraso", ascending=False)

# Sidebar
with st.sidebar:
    st.header("Configurações")
    loteria = st.selectbox("Loteria", list(LOTERIAS.keys()))
    cfg = LOTERIAS[loteria]
    st.markdown("---")
    modo = st.radio("Como montar o jogo", ["Montar manualmente", "Formulação Inteligente"])
    qtd_jogos = st.slider("Quantidade de jogos", 1, 10, 1)

# Último resultado
ultimo = buscar_ultimo(cfg["oficial_latest"])
if ultimo:
    col_a, col_b = st.columns([2,1])
    with col_a:
        st.markdown(f"### {loteria}")
        if ultimo.get("proximo") and ultimo["proximo"] != "N/A":
            st.markdown(f'<div class="premio-box"><div class="premio-valor">R$ {ultimo["proximo"]}</div><div>Prêmio estimado</div></div>', unsafe_allow_html=True)
        nums = " ".join(f"<span style='background:{cfg['cor']};color:white;padding:6px 10px;border-radius:50%;margin:2px;display:inline-block;font-weight:bold'>{n:02d}</span>" for n in sorted(ultimo["numeros"]))
        st.markdown(f"**Último concurso {ultimo['concurso']}** ({ultimo['data']})")
        st.markdown(nums, unsafe_allow_html=True)
        if cfg["dois_sorteios"] and ultimo.get("numeros2"):
            nums2 = " ".join(f"<span style='background:{cfg['cor']};color:white;padding:6px 10px;border-radius:50%;margin:2px;display:inline-block;font-weight:bold'>{n:02d}</span>" for n in sorted(ultimo["numeros2"]))
            st.markdown("**2º Sorteio:** " + nums2, unsafe_allow_html=True)

# Área de montagem
st.markdown("---")
if modo == "Montar manualmente":
    st.subheader("Monte seu jogo")
    if "selecionados" not in st.session_state:
        st.session_state.selecionados = set()
    
    # Grade de números
    cols = st.columns(10)
    for i, num in enumerate(range(cfg["min_num"], cfg["max_num"]+1)):
        with cols[i % 10]:
            sel = num in st.session_state.selecionados
            label = f"{'✓' if sel else ''}{num:02d}"
            if st.button(label, key=f"n{num}", use_container_width=True, type="primary" if sel else "secondary"):
                if sel:
                    st.session_state.selecionados.discard(num)
                else:
                    if len(st.session_state.selecionados) < cfg["qtd_numeros"]:
                        st.session_state.selecionados.add(num)
                st.rerun()
    
    st.markdown(f"**Selecionados:** {len(st.session_state.selecionados)} / {cfg['qtd_numeros']}")
    if st.button("Completar com números aleatórios", use_container_width=True):
        faltam = cfg["qtd_numeros"] - len(st.session_state.selecionados)
        if faltam > 0:
            disponiveis = [n for n in range(cfg["min_num"], cfg["max_num"]+1) if n not in st.session_state.selecionados]
            st.session_state.selecionados.update(random.sample(disponiveis, faltam))
            st.rerun()
    
    if len(st.session_state.selecionados) == cfg["qtd_numeros"]:
        jogo = sorted(st.session_state.selecionados)
        html = " ".join(f"<span style='background:{cfg['cor']};color:white;padding:8px 12px;border-radius:50%;margin:3px;display:inline-block;font-weight:bold'>{n:02d}</span>" for n in jogo)
        st.success("Jogo montado!")
        st.markdown(html, unsafe_allow_html=True)

else:
    st.subheader("Formulação Inteligente")
    if st.button("Carregar histórico e gerar", type="primary", use_container_width=True):
        with st.spinner("Analisando histórico..."):
            df = carregar_hist(cfg["json_url"], cfg["dois_sorteios"])
        if not df.empty:
            freq = analisar_freq(df, cfg["min_num"], cfg["max_num"])
            atraso = analisar_atraso(df, cfg["min_num"], cfg["max_num"])
            jogos = []
            for _ in range(qtd_jogos):
                # Equilibrado
                pesos = {}
                mf = freq["freq"].max() or 1
                ma = atraso["atraso"].max() or 1
                for _, r in freq.iterrows():
                    n = int(r["numero"])
                    pf = r["freq"] / mf
                    ar = atraso[atraso["numero"]==n]
                    pa = (ar["atraso"].values[0]/ma) if len(ar) else 0
                    pesos[n] = 0.55*pf + 0.45*pa
                nums = list(pesos.keys())
                p = np.array([pesos[n] for n in nums])
                p = p / p.sum()
                escolhidos = set()
                while len(escolhidos) < cfg["qtd_numeros"]:
                    escolhidos.add(np.random.choice(nums, p=p))
                jogos.append(sorted(escolhidos))
            st.session_state.jogos_intel = jogos
    
    if "jogos_intel" in st.session_state:
        st.markdown("### Jogos Inteligentes")
        for i, jogo in enumerate(st.session_state.jogos_intel, 1):
            html = " ".join(f"<span style='background:{cfg['cor']};color:white;padding:8px 12px;border-radius:50%;margin:3px;display:inline-block;font-weight:bold'>{n:02d}</span>" for n in jogo)
            st.markdown(f"**Jogo {i}**")
            st.markdown(html, unsafe_allow_html=True)
            st.markdown("")

st.caption("App de análise e formulação • Dados públicos da Caixa • Jogue com responsabilidade")
