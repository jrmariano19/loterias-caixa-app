import streamlit as st
import requests
import pandas as pd
import numpy as np
from collections import Counter
from datetime import datetime
import plotly.express as px
import random

st.set_page_config(
    page_title="Loterias Caixa Inteligente",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Disclaimer importante
st.warning("""
**⚠️ AVISO IMPORTANTE**  
Os sorteios das Loterias Caixa são **completamente aleatórios**.  
Análises de frequência, números "quentes/frios" ou atrasados **NÃO aumentam** a probabilidade real de acerto.  
Este aplicativo é apenas para **entretenimento e análise estatística** dos resultados históricos.  
Jogue com responsabilidade.
""")

st.title("🎲 Analisador Inteligente de Loterias Caixa")
st.markdown("Conectado aos dados oficiais e históricos das Loterias da Caixa Econômica Federal")

# Configurações das loterias
LOTERIAS = {
    "Mega-Sena": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/mega-sena.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/",
        "min_num": 1,
        "max_num": 60,
        "qtd_numeros": 6,
        "nome_curto": "megasena"
    },
    "Lotofácil": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotofacil.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/",
        "min_num": 1,
        "max_num": 25,
        "qtd_numeros": 15,
        "nome_curto": "lotofacil"
    },
    "Quina": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/quina.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/",
        "min_num": 1,
        "max_num": 80,
        "qtd_numeros": 5,
        "nome_curto": "quina"
    },
    "Lotomania": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotomania.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotomania/",
        "min_num": 0,
        "max_num": 99,
        "qtd_numeros": 20,
        "nome_curto": "lotomania"
    },
    "Dia de Sorte": {
        "json_url": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/dia-de-sorte.json",
        "oficial_latest": "https://servicebus2.caixa.gov.br/portaldeloterias/api/diadesorte/",
        "min_num": 1,
        "max_num": 31,
        "qtd_numeros": 7,
        "nome_curto": "diadesorte"
    }
}

@st.cache_data(ttl=3600)
def carregar_historico(url):
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        dados = resp.json()
        # Normalizar
        registros = []
        for item in dados:
            nums = [int(n) for n in item.get("resultado", [])]
            registros.append({
                "concurso": item.get("concurso"),
                "data": item.get("data"),
                "numeros": nums
            })
        return pd.DataFrame(registros).sort_values("concurso").reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def buscar_ultimo_oficial(url):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        dezenas = data.get("listaDezenas", [])
        return {
            "concurso": data.get("numero"),
            "data": data.get("dataApuracao"),
            "numeros": [int(n) for n in dezenas],
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
    freq["porcentagem"] = (freq["frequencia"] / (total_sorteios * df["numeros"].iloc[0].__len__() if total_sorteios else 1) * 100).round(2)
    return freq.sort_values("frequencia", ascending=False)

def calcular_atraso(df, min_n, max_n):
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

def gerar_jogo_ponderado(freq_df, atraso_df, qtd, min_n, max_n, peso_freq=0.6, peso_atraso=0.4, evitar_recentes=True, ultimos_n=5):
    """Gera um jogo usando pesos baseados em frequência e atraso."""
    pesos = {}
    max_freq = freq_df["frequencia"].max() or 1
    max_atraso = atraso_df["atraso_concursos"].max() or 1
    
    for _, row in freq_df.iterrows():
        num = int(row["numero"])
        peso_f = row["frequencia"] / max_freq
        atraso_row = atraso_df[atraso_df["numero"] == num]
        peso_a = atraso_row["atraso_concursos"].values[0] / max_atraso if len(atraso_row) else 0
        pesos[num] = peso_freq * peso_f + peso_atraso * peso_a
    
    # Normalizar
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
    st.header("⚙️ Configurações")
    loteria_selecionada = st.selectbox("Escolha a Loteria", list(LOTERIAS.keys()))
    config = LOTERIAS[loteria_selecionada]
    
    st.subheader("Gerador de Jogos")
    qtd_jogos = st.slider("Quantidade de jogos a gerar", 1, 20, 5)
    estrategia = st.radio(
        "Estratégia de geração",
        ["Equilibrada (Frequência + Atraso)", "Números Quentes (mais frequentes)", "Números Frios/Atrasados", "Aleatório Puro"]
    )
    
    st.markdown("---")
    st.caption("Dados históricos via [loterias.json](https://github.com/eitchtee/loterias.json)")
    st.caption("Último resultado via API oficial Caixa")

# Conteúdo principal
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader(f"📊 Último Resultado - {loteria_selecionada}")
    ultimo = buscar_ultimo_oficial(config["oficial_latest"])
    if "erro" in ultimo:
        st.error(f"Não foi possível buscar o último resultado oficial: {ultimo['erro']}")
    else:
        st.metric("Concurso", ultimo.get("concurso", "N/A"))
        st.write(f"**Data:** {ultimo.get('data', 'N/A')}")
        nums_str = " - ".join(f"{n:02d}" for n in sorted(ultimo.get("numeros", [])))
        st.success(f"**Números:** {nums_str}")
        if ultimo.get("acumulado"):
            st.info("🔴 Acumulou!")
        else:
            st.info("🟢 Teve ganhador(es)")

with col2:
    st.subheader("📈 Estatísticas Rápidas")
    if st.button("Carregar e Analisar Histórico", type="primary"):
        with st.spinner("Carregando dados históricos..."):
            df = carregar_historico(config["json_url"])
        
        if df.empty:
            st.error("Não foi possível carregar o histórico.")
        else:
            st.session_state.df = df
            st.session_state.config = config
            st.success(f"✅ Carregados **{len(df)}** concursos históricos")
            st.write(f"Do concurso {df['concurso'].min()} até {df['concurso'].max()}")

# Se dados carregados
if "df" in st.session_state and st.session_state.config == config:
    df = st.session_state.df
    config = st.session_state.config
    
    tab1, tab2, tab3, tab4 = st.tabs(["Frequência", "Atrasos", "Gerar Jogos", "Histórico Recente"])
    
    with tab1:
        st.subheader("Números mais e menos frequentes")
        freq = analisar_frequencia(df, config["min_num"], config["max_num"])
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**🔥 Mais frequentes**")
            st.dataframe(freq.head(15).style.format({"porcentagem": "{:.2f}%"}), use_container_width=True)
        with col_b:
            st.write("**❄️ Menos frequentes**")
            st.dataframe(freq.tail(15).sort_values("frequencia").style.format({"porcentagem": "{:.2f}%"}), use_container_width=True)
        
        fig = px.bar(freq.head(30), x="numero", y="frequencia", title="Top 30 números mais frequentes")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Números mais atrasados")
        atraso = calcular_atraso(df, config["min_num"], config["max_num"])
        st.dataframe(atraso.head(20), use_container_width=True)
        fig2 = px.bar(atraso.head(25), x="numero", y="atraso_concursos", title="Maiores atrasos (concursos sem sair)")
        st.plotly_chart(fig2, use_container_width=True)
    
    with tab3:
        st.subheader("🎯 Gerar Jogos com Tendência")
        if st.button("Gerar Jogos Agora", type="primary"):
            freq = analisar_frequencia(df, config["min_num"], config["max_num"])
            atraso = calcular_atraso(df, config["min_num"], config["max_num"])
            
            jogos = []
            for i in range(qtd_jogos):
                if estrategia == "Aleatório Puro":
                    jogo = sorted(random.sample(range(config["min_num"], config["max_num"]+1), config["qtd_numeros"]))
                elif estrategia == "Números Quentes (mais frequentes)":
                    top = freq.head(config["qtd_numeros"] + 10)["numero"].tolist()
                    jogo = sorted(random.sample(top, config["qtd_numeros"]))
                elif estrategia == "Números Frios/Atrasados":
                    top = atraso.head(config["qtd_numeros"] + 10)["numero"].tolist()
                    jogo = sorted(random.sample(top, config["qtd_numeros"]))
                else:  # Equilibrada
                    jogo = gerar_jogo_ponderado(
                        freq, atraso, config["qtd_numeros"],
                        config["min_num"], config["max_num"]
                    )
                jogos.append(jogo)
            
            st.session_state.jogos_gerados = jogos
        
        if "jogos_gerados" in st.session_state:
            for idx, jogo in enumerate(st.session_state.jogos_gerados, 1):
                nums_fmt = " - ".join(f"{n:02d}" for n in jogo)
                st.code(f"Jogo {idx}: {nums_fmt}", language=None)
            
            st.download_button(
                "📥 Baixar jogos como TXT",
                "\n".join(" - ".join(f"{n:02d}" for n in j) for j in st.session_state.jogos_gerados),
                file_name=f"jogos_{config['nome_curto']}.txt",
                mime="text/plain"
            )
    
    with tab4:
        st.subheader("Últimos 15 resultados")
        recentes = df.tail(15).iloc[::-1]
        for _, row in recentes.iterrows():
            nums = " - ".join(f"{n:02d}" for n in sorted(row["numeros"]))
            st.write(f"**Concurso {row['concurso']}** ({row['data']}): `{nums}`")

else:
    st.info("👆 Clique em **Carregar e Analisar Histórico** na barra lateral para começar a análise e gerar jogos.")

st.markdown("---")
st.caption("Desenvolvido para análise estatística • Dados públicos da Caixa e repositório comunitário • Jogue com responsabilidade")
