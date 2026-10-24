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
.bolinha {display:inline-block; width:42px; height:42px; border-radius:50%; background:#00A651; color:white; text-align:center; line-height:42px; font-weight:bold; margin:3px; font-size:0.95rem;}
.bolinha-vazia {display:inline-block; width:42px; height:42px; border-radius:50%; border:2px solid #00A651; color:#00A651; text-align:center; line-height:38px; font-weight:bold; margin:3px; background:white;}
.premio {font-size:1.6rem; font-weight:800; color:#00A651; text-align:center;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header"><h2 style="margin:0">🍀 Loterias Caixa</h2></div>', unsafe_allow_html=True)

LOTERIAS = {
    "Mega-Sena": {"api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/", "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/mega-sena.json", "min":1, "max":60, "qtd":6, "cor":"#00A651"},
    "Lotofácil": {"api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/", "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotofacil.json", "min":1, "max":25, "qtd":15, "cor":"#9B1B6E"},
    "Quina": {"api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/", "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/quina.json", "min":1, "max":80, "qtd":5, "cor":"#4B0082"},
    "Dupla Sena": {"api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena/", "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/dupla-sena.json", "min":1, "max":50, "qtd":6, "cor":"#C41E3A"},
}

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
    if "sel" not in st.session_state:
        st.session_state.sel = set()

    # Grade mais compacta
    cols_per_row = 8 if cfg["max"] > 40 else 5
    nums_range = list(range(cfg["min"], cfg["max"]+1))
    for i in range(0, len(nums_range), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, num in enumerate(nums_range[i:i+cols_per_row]):
            with cols[j]:
                selected = num in st.session_state.sel
                btn_label = f"✓{num:02d}" if selected else f"{num:02d}"
                if st.button(btn_label, key=f"btn_{num}", use_container_width=True, type="primary" if selected else "secondary"):
                    if selected:
                        st.session_state.sel.discard(num)
                    elif len(st.session_state.sel) < cfg["qtd"]:
                        st.session_state.sel.add(num)
                    st.rerun()

    st.write(f"**Selecionados: {len(st.session_state.sel)} / {cfg['qtd']}**")
    
    if st.button("Completar aleatório", use_container_width=True):
        faltam = cfg["qtd"] - len(st.session_state.sel)
        if faltam > 0:
            disp = [n for n in nums_range if n not in st.session_state.sel]
            st.session_state.sel.update(random.sample(disp, min(faltam, len(disp))))
            st.rerun()

    if len(st.session_state.sel) == cfg["qtd"]:
        jogo = sorted(st.session_state.sel)
        html = "".join(f'<span class="bolinha" style="background:{cfg["cor"]}">{n:02d}</span>' for n in jogo)
        st.success("Jogo pronto!")
        st.markdown(html, unsafe_allow_html=True)
        if st.button("Limpar jogo"):
            st.session_state.sel = set()
            st.rerun()

else:
    st.subheader("Formulação Inteligente")
    qtd = st.slider("Quantidade de jogos", 1, 10, 3)
    if st.button("Gerar jogos inteligentes", type="primary", use_container_width=True):
        with st.spinner("Analisando..."):
            try:
                r = requests.get(cfg["json"], timeout=20)
                dados = r.json()
                todos = []
                for item in dados:
                    todos.extend([int(x) for x in item.get("resultado", item.get("resultado_1", []))])
                cont = Counter(todos)
                # Top números + um pouco de aleatório
                top = [n for n,_ in cont.most_common(cfg["qtd"]+10)]
                jogos = []
                for _ in range(qtd):
                    jogo = sorted(random.sample(top, cfg["qtd"]))
                    jogos.append(jogo)
                st.session_state.intel = jogos
            except:
                st.error("Erro ao carregar dados")
    
    if "intel" in st.session_state:
        for i, jogo in enumerate(st.session_state.intel, 1):
            html = "".join(f'<span class="bolinha" style="background:{cfg["cor"]}">{n:02d}</span>' for n in jogo)
            st.markdown(f"**Jogo {i}**")
            st.markdown(html, unsafe_allow_html=True)
            st.write("")

st.caption("Análise estatística • Jogue com responsabilidade")
