import streamlit as st
import requests
import pandas as pd
import numpy as np
from collections import Counter
import plotly.express as px
import random

st.set_page_config(
    page_title="Loterias Caixa | Analisador",
    page_icon="🍀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS profissional inspirado nas Loterias Caixa
st.markdown("""
<style>
    .stApp {
        background-color: #f5f7fa;
    }
    .main-header {
        background: linear-gradient(90deg, #006B3F 0%, #00A651 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(0,107,63,0.25);
    }
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 0.3rem 0 0 0;
        opacity: 0.9;
        font-size: 1rem;
    }
    .result-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 5px solid #00A651;
    }
    .stButton>button {
        background-color: #00A651;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #008C44;
        color: white;
    }
    div[data-testid="stMetricValue"] {
        color: #006B3F;
        font-weight: 700;
    }
    .disclaimer {
        background: #fff8e6;
        border-left: 4px solid #f0ad4e;
        padding: 0.8rem 1rem;
        border-radius: 6px;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Header profissional
st.markdown("""
<div class="main-header">
    <h1>🍀 Loterias Caixa</h1>
    <p>Analisador Inteligente de Resultados e Gerador de Jogos</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="disclaimer">
    <strong>Aviso:</strong> Os sorteios são aleatórios. Análises de frequência e atrasos <strong>não aumentam</strong> a chance real de acerto. 
    Este aplicativo é apenas para entretenimento e análise estatística. Jogue com responsabilidade.
</div>
""", unsafe_allow_html=True)

# Configurações das loterias
LOTERIAS = {
    "Mega-Sena": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/mega-sena.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/",
        "min_num": 1, "max_num": 60, "qtd_numeros": 6, "nome_curto": "megasena", "cor": "#00A651", "dois_sorteios": False
    },
    "Lotofácil": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotofacil.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/",
        "min_num": 1, "max_num": 25, "qtd_numeros": 15, "nome_curto": "lotofacil", "cor": "#9B1B6E", "dois_sorteios": False
    },
    "Quina": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/quina.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/",
        "min_num": 1, "max_num": 80, "qtd_numeros": 5, "nome_curto": "quina", "cor": "#4B0082", "dois_sorteios": False
    },
    "Dupla Sena": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/dupla-sena.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena/",
        "min_num": 1, "max_num": 50, "qtd_numeros": 6, "nome_curto": "duplasena", "cor": "#C41E3A", "dois_sorteios": True
    },
    "Lotomania": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotomania.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotomania/",
        "min_num": 0, "max_num": 99, "qtd_numeros": 20, "nome_curto": "lotomania", "cor": "#FF6B00", "dois_sorteios": False
    },
    "Dia de Sorte": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/dia-de-sorte.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/diadesorte/",
        "min_num": 1, "max_num": 31, "qtd_numeros": 7, "nome_curto": "diadesorte", "cor": "#FFD700", "dois_sorteios": False
    }
}

@st.cache_data(ttl=3600)
def carregar_historico(url, dois_sorteios=False):
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        dados = resp.json()
        registros = []
        for item in dados:
            if dois_sorteios:
                nums1 = [int(n) for n in item.get("resultado_1", item.get("resultado", []))]
                nums2 = [int(n) for n in item.get("resultado_2", [])]
                registros.append({
                    "concurso": item.get("concurso"),
                    "data": item.get("data"),
                    "numeros": nums1,
                    "numeros2": nums2
                })
            else:
                nums = [int(n) for n in item.get("resultado", [])]
                registros.append({
                    "concurso": item.get("concurso"),
                    "data": item.get("data"),
                    "numeros": nums,
                    "numeros2": []
                })
        return pd.DataFrame(registros).sort_values("concurso").reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def buscar_ultimo_oficial(url, dois_sorteios=False):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        dezenas = data.get("listaDezenas", [])
        dezenas2 = data.get("listaDezenasSegundoSorteio", []) or []
        return {
            "concurso": data.get("numero"),
            "data": data.get("dataApuracao"),
            "numeros": [int(n) for n in dezenas],
            "numeros2": [int(n) for n in dezenas2] if dois_sorteios else [],
            "acumulado": data.get("acumulado", False),
            "proximo_valor": data.get("valorEstimadoProximoConcurso", "N/A"),
            "data_proximo": data.get("dataProximoConcurso")
        }
    except Exception as e:
        return {"erro": str(e)}

def analisar_frequencia(df, min_n, max_n):
    todos = []
    for nums in df["numeros"]:
        todos.extend(nums)
    contagem = Counter(todos)
    freq = pd.DataFrame({
        "numero": range(min_n, max_n + 1),
        "frequencia": [contagem.get(i, 0) for i in range(min_n, max_n + 1)]
    })
    total_sorteios = len(df)
    if total_sorteios and len(df) > 0:
        qtd = len(df["numeros"].iloc[0])
        freq["porcentagem"] = (freq["frequencia"] / (total_sorteios * qtd) * 100).round(2)
    else:
        freq["porcentagem"] = 0
    return freq.sort_values("frequencia", ascending=False)

def calcular_atraso(df, min_n, max_n):
    if df.empty:
        return pd.DataFrame()
    ultimo_concurso = df["concurso"].max()
    atrasos = {}
    for num in range(min_n, max_n + 1):
        aparicoes = df[df["numeros"].apply(lambda x: num in x)]
        if len(aparicoes) == 0:
            atrasos[num] = ultimo_concurso
        else:
            atrasos[num] = ultimo_concurso - aparicoes["concurso"].max()
    return pd.DataFrame({
        "numero": list(atrasos.keys()),
        "atraso_concursos": list(atrasos.values())
    }).sort_values("atraso_concursos", ascending=False)

def gerar_jogo_ponderado(freq_df, atraso_df, qtd, min_n, max_n, peso_freq=0.6, peso_atraso=0.4):
    pesos = {}
    max_freq = freq_df["frequencia"].max() or 1
    max_atraso = atraso_df["atraso_concursos"].max() or 1
    for _, row in freq_df.iterrows():
        num = int(row["numero"])
        peso_f = row["frequencia"] / max_freq
        atraso_row = atraso_df[atraso_df["numero"] == num]
        peso_a = atraso_row["atraso_concursos"].values[0] / max_atraso if len(atraso_row) else 0
        pesos[num] = peso_freq * peso_f + peso_atraso * peso_a
    numeros = list(pesos.keys())
    pesos_list = np.array([pesos[n] for n in numeros])
    pesos_list = pesos_list / pesos_list.sum()
    escolhidos = set()
    tentativas = 0
    while len(escolhidos) < qtd and tentativas < 1000:
        cand = np.random.choice(numeros, p=pesos_list)
        if cand not in escolhidos:
            escolhidos.add(cand)
        tentativas += 1
    return sorted(list(escolhidos))[:qtd]

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Configurações")
    loteria_selecionada = st.selectbox("Escolha a Loteria", list(LOTERIAS.keys()))
    config = LOTERIAS[loteria_selecionada]
    
    st.markdown("---")
    st.markdown("### 🎯 Formular Jogos")
    qtd_jogos = st.slider("Quantidade de jogos", 1, 20, 5)
    
    modo_geracao = st.radio(
        "Modo de formulação",
        ["Formulação Normal", "Formulação Inteligente"],
        help="Normal: gera de forma simples. Inteligente: analisa o histórico e prioriza números com tendência."
    )
    
    if modo_geracao == "Formulação Inteligente":
        estrategia = st.selectbox(
            "Tipo de análise inteligente",
            ["Equilibrada (Frequência + Atraso)", "Números Quentes (mais saíram)", "Números Atrasados (há mais tempo sem sair)"]
        )
    else:
        estrategia = "Aleatório"
    
    st.markdown("---")
    st.caption("Dados oficiais da Caixa + histórico público")

# Conteúdo principal
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 📊 Último Resultado")
    ultimo = buscar_ultimo_oficial(config["oficial_latest"], config.get("dois_sorteios", False))
    if "erro" in ultimo:
        st.error(f"Não foi possível buscar o último resultado: {ultimo['erro']}")
    else:
        st.metric("Concurso", ultimo.get("concurso", "N/A"))
        st.write(f"**Data:** {ultimo.get('data', 'N/A')}")
        
        nums = sorted(ultimo.get("numeros", []))
        nums_html = " ".join([f'<span style="background:{config["cor"]};color:white;padding:6px 10px;border-radius:50%;font-weight:bold;margin:2px;display:inline-block;">{n:02d}</span>' for n in nums])
        st.markdown("**1º Sorteio:**" if config.get("dois_sorteios") else "**Números:**", unsafe_allow_html=True)
        st.markdown(nums_html, unsafe_allow_html=True)
        
        if config.get("dois_sorteios") and ultimo.get("numeros2"):
            nums2 = sorted(ultimo.get("numeros2", []))
            nums2_html = " ".join([f'<span style="background:{config["cor"]};color:white;padding:6px 10px;border-radius:50%;font-weight:bold;margin:2px;display:inline-block;">{n:02d}</span>' for n in nums2])
            st.markdown("**2º Sorteio:**", unsafe_allow_html=True)
            st.markdown(nums2_html, unsafe_allow_html=True)
        
        if ultimo.get("acumulado"):
            st.info("🔴 Acumulou")
        else:
            st.success("🟢 Teve ganhador(es)")

with col2:
    st.markdown("### 📈 Análise")
    if st.button("Carregar Histórico Completo", type="primary", use_container_width=True):
        with st.spinner("Carregando dados históricos..."):
            df = carregar_historico(config["json_url"], config.get("dois_sorteios", False))
        if df.empty:
            st.error("Não foi possível carregar o histórico.")
        else:
            st.session_state.df = df
            st.session_state.config = config
            st.success(f"✅ {len(df)} concursos carregados")

# Tabs de análise
if "df" in st.session_state and st.session_state.get("config") == config:
    df = st.session_state.df
    config = st.session_state.config
    
    tab1, tab2, tab3, tab4 = st.tabs(["Frequência", "Atrasos", "Gerar Jogos", "Histórico"])
    
    with tab1:
        st.markdown("#### Números mais e menos frequentes")
        freq = analisar_frequencia(df, config["min_num"], config["max_num"])
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🔥 Mais frequentes**")
            st.dataframe(freq.head(15), use_container_width=True, hide_index=True)
        with c2:
            st.markdown("**❄️ Menos frequentes**")
            st.dataframe(freq.tail(15).sort_values("frequencia"), use_container_width=True, hide_index=True)
        fig = px.bar(freq.head(25), x="numero", y="frequencia", title="Top 25 mais frequentes",
                     color_discrete_sequence=[config["cor"]])
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.markdown("#### Números mais atrasados")
        atraso = calcular_atraso(df, config["min_num"], config["max_num"])
        st.dataframe(atraso.head(20), use_container_width=True, hide_index=True)
        fig2 = px.bar(atraso.head(20), x="numero", y="atraso_concursos", title="Maiores atrasos",
                      color_discrete_sequence=["#FF6B00"])
        st.plotly_chart(fig2, use_container_width=True)
    
    with tab3:
        st.markdown("#### Formular Jogos")
        st.info(f"**Modo selecionado:** {modo_geracao}" + (f" → {estrategia}" if modo_geracao == "Formulação Inteligente" else ""))
        
        if st.button("Gerar Jogos Agora", type="primary", use_container_width=True):
            if "df" not in st.session_state:
                st.warning("Carregue o histórico primeiro para usar a Formulação Inteligente.")
            else:
                freq = analisar_frequencia(df, config["min_num"], config["max_num"])
                atraso = calcular_atraso(df, config["min_num"], config["max_num"])
                jogos = []
                for _ in range(qtd_jogos):
                    if modo_geracao == "Formulação Normal" or estrategia == "Aleatório":
                        jogo = sorted(random.sample(range(config["min_num"], config["max_num"]+1), config["qtd_numeros"]))
                    elif "Quentes" in estrategia:
                        top = freq.head(config["qtd_numeros"] + 8)["numero"].tolist()
                        jogo = sorted(random.sample(top, config["qtd_numeros"]))
                    elif "Atrasados" in estrategia:
                        top = atraso.head(config["qtd_numeros"] + 8)["numero"].tolist()
                        jogo = sorted(random.sample(top, config["qtd_numeros"]))
                    else:  # Equilibrada
                        jogo = gerar_jogo_ponderado(freq, atraso, config["qtd_numeros"], config["min_num"], config["max_num"])
                    jogos.append(jogo)
                st.session_state.jogos_gerados = jogos
        
        if "jogos_gerados" in st.session_state and st.session_state.jogos_gerados:
            st.markdown("---")
            st.markdown("### 🎫 Jogos Formulados")
            for idx, jogo in enumerate(st.session_state.jogos_gerados, 1):
                with st.container():
                    st.markdown(f"**Jogo {idx}**")
                    nums_html = " ".join([
                        f'<span style="background:{config["cor"]};color:white;padding:8px 12px;border-radius:50%;font-weight:bold;margin:3px;display:inline-block;font-size:1.1rem;min-width:40px;text-align:center;">{n:02d}</span>'
                        for n in jogo
                    ])
                    st.markdown(f'<div style="line-height:2.8;">{nums_html}</div>', unsafe_allow_html=True)
                    st.markdown("")
            
            st.markdown("---")
            txt = "\n".join(" - ".join(f"{n:02d}" for n in j) for j in st.session_state.jogos_gerados)
            st.download_button(
                "📥 Baixar todos os jogos (.txt)",
                txt,
                file_name=f"jogos_{config['nome_curto']}_{modo_geracao.replace(' ', '_').lower()}.txt",
                use_container_width=True
            )
    
    with tab4:
        st.markdown("#### Últimos resultados")
        recentes = df.tail(12).iloc[::-1]
        for _, row in recentes.iterrows():
            nums = sorted(row["numeros"])
            nums_str = " ".join(f"{n:02d}" for n in nums)
            st.write(f"**{row['concurso']}** ({row['data']}): `{nums_str}`")

else:
    st.info("👆 Clique em **Carregar Histórico Completo** para começar a análise.")

st.markdown("---")
st.caption("Analisador de Loterias Caixa • Dados públicos • Jogue com responsabilidade")
