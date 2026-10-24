import streamlit as st
import requests
import random
from collections import Counter

st.set_page_config(page_title="Loterias Caixa", page_icon="🍀", layout="centered")

st.markdown("""
<style>
.header {background: linear-gradient(90deg,#006B3F,#00A651); color:white; padding:1rem; border-radius:12px; margin-bottom:1rem;}
.bolinha {display:inline-block; width:42px; height:42px; border-radius:50%; background:#00A651; color:white; text-align:center; line-height:42px; font-weight:bold; margin:3px; font-size:0.95rem;}
.premio {font-size:1.5rem; font-weight:800; color:#00A651; text-align:center;}
/* Força botões menores e em grade */
div[data-testid="column"] button {
    min-width: 48px !important;
    height: 48px !important;
    padding: 0 !important;
    font-size: 0.9rem !important;
    font-weight: bold !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header"><h2 style="margin:0">🍀 Loterias Caixa</h2></div>', unsafe_allow_html=True)

LOTERIAS = {
    "Mega-Sena": {"api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/", "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/mega-sena.json", "min":1, "max":60, "qtd":6, "cor":"#00A651"},
    "Lotofácil": {"api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/", "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotofacil.json", "min":1, "max":25, "qtd":15, "cor":"#9B1B6E"},
    "Quina": {"api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/", "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/quina.json", "min":1, "max":80, "qtd":5, "cor":"#4B0082"},
    "Dupla Sena": {"api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena/", "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/dupla-sena.json", "min":1, "max":50, "qtd":6, "cor":"#C41E3A"},
}

if "jogos_salvos" not in st.session_state:
    st.session_state.jogos_salvos = []
if "sel" not in st.session_state:
    st.session_state.sel = set()

loteria = st.selectbox("Loteria", list(LOTERIAS.keys()))
cfg = LOTERIAS[loteria]

@st.cache_data(ttl=300)
def get_ultimo(url):
    try:
        r = requests.get(url, timeout=10)
        d = r.json()
        return d.get("numero"), d.get("dataApuracao"), [int(x) for x in d.get("listaDezenas",[])], d.get("valorEstimadoProximoConcurso")
    except:
        return None, None, [], None

conc, data, nums, premio = get_ultimo(cfg["api"])
if conc:
    if premio:
        st.markdown(f'<div class="premio">R$ {premio}</div>', unsafe_allow_html=True)
        st.caption("Prêmio estimado", unsafe_allow_html=False)
    st.write(f"**Último concurso {conc}** ({data})")
    html = "".join(f'<span class="bolinha" style="background:{cfg["cor"]}">{n:02d}</span>' for n in sorted(nums))
    st.markdown(html, unsafe_allow_html=True)

st.markdown("---")
modo = st.radio("Modo", ["Montar jogo", "Formulação Inteligente"], horizontal=True)

if modo == "Montar jogo":
    st.subheader("Selecione os números")
    
    # Grade com 5 colunas (melhor no celular)
    cols_per_row = 5
    nums_range = list(range(cfg["min"], cfg["max"]+1))
    
    for i in range(0, len(nums_range), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, num in enumerate(nums_range[i:i+cols_per_row]):
            with cols[j]:
                selected = num in st.session_state.sel
                if st.button(f"{num:02d}", key=f"n{num}", type="primary" if selected else "secondary", use_container_width=True):
                    if selected:
                        st.session_state.sel.discard(num)
                    elif len(st.session_state.sel) < cfg["qtd"]:
                        st.session_state.sel.add(num)
                    st.rerun()

    st.write(f"**Selecionados: {len(st.session_state.sel)} / {cfg['qtd']}**")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Completar aleatório", use_container_width=True):
            faltam = cfg["qtd"] - len(st.session_state.sel)
            if faltam > 0:
                disp = [n for n in nums_range if n not in st.session_state.sel]
                st.session_state.sel.update(random.sample(disp, min(faltam, len(disp))))
                st.rerun()
    with col2:
        if st.button("Limpar", use_container_width=True):
            st.session_state.sel = set()
            st.rerun()

    if len(st.session_state.sel) == cfg["qtd"]:
        jogo = sorted(list(st.session_state.sel))
        html = "".join(f'<span class="bolinha" style="background:{cfg["cor"]}">{n:02d}</span>' for n in jogo)
        st.success("Jogo pronto!")
        st.markdown(html, unsafe_allow_html=True)
        if st.button("💾 Salvar jogo", type="primary", use_container_width=True):
            st.session_state.jogos_salvos.append({"loteria": loteria, "numeros": jogo, "modo": "Manual"})
            st.session_state.sel = set()
            st.rerun()

else:
    st.subheader("Formulação Inteligente")
    qtd = st.slider("Quantidade", 1, 8, 3)
    if st.button("Gerar jogos", type="primary", use_container_width=True):
        with st.spinner("Analisando..."):
            try:
                r = requests.get(cfg["json"], timeout=15)
                dados = r.json()
                todos = []
                for item in dados:
                    res = item.get("resultado") or item.get("resultado_1") or []
                    todos.extend([int(x) for x in res])
                top = [n for n,_ in Counter(todos).most_common(cfg["qtd"]+10)]
                st.session_state.intel = [sorted(random.sample(top, cfg["qtd"])) for _ in range(qtd)]
            except:
                st.error("Erro ao carregar histórico")
    
    if "intel" in st.session_state:
        for i, jogo in enumerate(st.session_state.intel, 1):
            html = "".join(f'<span class="bolinha" style="background:{cfg["cor"]}">{n:02d}</span>' for n in jogo)
            st.markdown(f"**Jogo {i}**")
            st.markdown(html, unsafe_allow_html=True)
            if st.button(f"Salvar {i}", key=f"s{i}"):
                st.session_state.jogos_salvos.append({"loteria": loteria, "numeros": jogo, "modo": "Inteligente"})
                st.rerun()

if st.session_state.jogos_salvos:
    st.markdown("---")
    st.subheader("Jogos Salvos")
    for idx, j in enumerate(st.session_state.jogos_salvos):
        html = "".join(f'<span class="bolinha" style="background:{LOTERIAS[j["loteria"]]["cor"]}">{n:02d}</span>' for n in j["numeros"])
        c1, c2 = st.columns([5,1])
        with c1:
            st.markdown(f"**{j['loteria']}** • {j['modo']}")
            st.markdown(html, unsafe_allow_html=True)
        with c2:
            if st.button("🗑️", key=f"d{idx}"):
                st.session_state.jogos_salvos.pop(idx)
                st.rerun()

st.caption("Jogue com responsabilidade")
