import streamlit as st
import requests
import pandas as pd
import numpy as np
from collections import Counter
import random

st.set_page_config(page_title="Loterias Caixa", page_icon="🍀", layout="centered")

st.markdown("""
<style>
.header {background: linear-gradient(90deg,#006B3F,#00A651); color:white; padding:1rem; border-radius:12px; margin-bottom:1rem;}
.bolinha {display:inline-block; width:44px; height:44px; border-radius:50%; background:#00A651; color:white; text-align:center; line-height:44px; font-weight:bold; margin:4px; font-size:1rem;}
.premio {font-size:1.6rem; font-weight:800; color:#00A651; text-align:center;}
div[data-testid="stButton"] > button {
    border-radius: 50% !important;
    width: 52px !important;
    height: 52px !important;
    min-width: 52px !important;
    padding: 0 !important;
    font-weight: bold !important;
    margin: 2px auto !important;
    display: block !important;
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

loteria = st.selectbox("Escolha a Loteria", list(LOTERIAS.keys()))
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
        st.markdown(f'<div class="premio">R$ {premio}</div><p style="text-align:center">Prêmio estimado</p>', unsafe_allow_html=True)
    st.write(f"**Último concurso {conc}** ({data})")
    html = "".join(f'<span class="bolinha" style="background:{cfg["cor"]}">{n:02d}</span>' for n in sorted(nums))
    st.markdown(html, unsafe_allow_html=True)

st.markdown("---")
modo = st.radio("Modo", ["Montar jogo", "Formulação Inteligente"], horizontal=True)

if modo == "Montar jogo":
    st.subheader("Selecione os números")
    
    cols_per_row = 6
    nums_range = list(range(cfg["min"], cfg["max"]+1))
    for i in range(0, len(nums_range), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, num in enumerate(nums_range[i:i+cols_per_row]):
            with cols[j]:
                selected = num in st.session_state.sel
                label = f"{num:02d}"
                if st.button(label, key=f"btn_{num}", type="primary" if selected else "secondary"):
                    if selected:
                        st.session_state.sel.discard(num)
                    elif len(st.session_state.sel) < cfg["qtd"]:
                        st.session_state.sel.add(num)
                    st.rerun()

    st.write(f"**Selecionados: {len(st.session_state.sel)} / {cfg['qtd']}**")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Completar aleatório", use_container_width=True):
            faltam = cfg["qtd"] - len(st.session_state.sel)
            if faltam > 0:
                disp = [n for n in nums_range if n not in st.session_state.sel]
                st.session_state.sel.update(random.sample(disp, min(faltam, len(disp))))
                st.rerun()
    with c2:
        if st.button("Limpar", use_container_width=True):
            st.session_state.sel = set()
            st.rerun()

    if len(st.session_state.sel) == cfg["qtd"]:
        jogo = sorted(st.session_state.sel)
        html = "".join(f'<span class="bolinha" style="background:{cfg["cor"]}">{n:02d}</span>' for n in jogo)
        st.success("Jogo pronto!")
        st.markdown(html, unsafe_allow_html=True)
        if st.button("💾 Salvar este jogo", type="primary", use_container_width=True):
            st.session_state.jogos_salvos.append({"loteria": loteria, "numeros": jogo, "modo": "Manual"})
            st.session_state.sel = set()
            st.success("Jogo salvo!")
            st.rerun()

else:
    st.subheader("Formulação Inteligente")
    qtd = st.slider("Quantidade de jogos", 1, 10, 3)
    if st.button("Gerar jogos inteligentes", type="primary", use_container_width=True):
        with st.spinner("Analisando histórico..."):
            try:
                r = requests.get(cfg["json"], timeout=20)
                dados = r.json()
                todos = []
                for item in dados:
                    res = item.get("resultado") or item.get("resultado_1") or []
                    todos.extend([int(x) for x in res])
                cont = Counter(todos)
                top = [n for n,_ in cont.most_common(cfg["qtd"]+12)]
                jogos = []
                for _ in range(qtd):
                    jogos.append(sorted(random.sample(top, cfg["qtd"])))
                st.session_state.intel_temp = jogos
            except Exception as e:
                st.error("Erro ao carregar dados")
    
    if "intel_temp" in st.session_state:
        for i, jogo in enumerate(st.session_state.intel_temp, 1):
            html = "".join(f'<span class="bolinha" style="background:{cfg["cor"]}">{n:02d}</span>' for n in jogo)
            st.markdown(f"**Jogo {i}**")
            st.markdown(html, unsafe_allow_html=True)
            if st.button(f"💾 Salvar jogo {i}", key=f"save_{i}"):
                st.session_state.jogos_salvos.append({"loteria": loteria, "numeros": jogo, "modo": "Inteligente"})
                st.success(f"Jogo {i} salvo!")
                st.rerun()
            st.write("")

# Jogos salvos
if st.session_state.jogos_salvos:
    st.markdown("---")
    st.subheader("📋 Jogos Salvos")
    for idx, j in enumerate(st.session_state.jogos_salvos):
        html = "".join(f'<span class="bolinha" style="background:{LOTERIAS[j["loteria"]]["cor"]}">{n:02d}</span>' for n in j["numeros"])
        colx, coly = st.columns([4,1])
        with colx:
            st.markdown(f"**{j['loteria']}** ({j['modo']})")
            st.markdown(html, unsafe_allow_html=True)
        with coly:
            if st.button("🗑️", key=f"del_{idx}"):
                st.session_state.jogos_salvos.pop(idx)
                st.rerun()
        st.write("")

st.caption("Análise estatística • Jogue com responsabilidade")
