import random
from collections import Counter

import requests
import streamlit as st

st.set_page_config(page_title="Loterias Caixa", page_icon="🍀", layout="centered")

LOTERIAS = {
    "Mega-Sena": {
        "api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/",
        "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/mega-sena.json",
        "min": 1,
        "max": 60,
        "qtd": 6,
        "premio_min": 4,
        "cor": "#008A45",
        "dois": False,
    },
    "Lotofácil": {
        "api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/",
        "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotofacil.json",
        "min": 1,
        "max": 25,
        "qtd": 15,
        "premio_min": 11,
        "cor": "#8E1A64",
        "dois": False,
    },
    "Quina": {
        "api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/",
        "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/quina.json",
        "min": 1,
        "max": 80,
        "qtd": 5,
        "premio_min": 2,
        "cor": "#3C2778",
        "dois": False,
    },
    "Dupla Sena": {
        "api": "https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena/",
        "json": "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/dupla-sena.json",
        "min": 1,
        "max": 50,
        "qtd": 6,
        "premio_min": 3,
        "cor": "#9D1C38",
        "dois": True,
    },
}


def brl(value, digits):
    text = f"{value:,.{digits}f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def balls(nums, color):
    return "".join(
        f'<span class="bolinha" style="background:{color}">{int(n):02d}</span>' for n in nums
    )


def hits(game, draw):
    drawn = set(draw)
    return sum(1 for n in game if n in drawn)


def hit_phrase(count, where):
    if count == 0:
        return f"Nenhum acerto {where}"
    if count == 1:
        return f"1 acerto {where}"
    return f"{count} acertos {where}"


def to_nums(value):
    if not isinstance(value, list):
        return []
    nums = []
    for item in value:
        try:
            nums.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(nums)


@st.cache_data(ttl=60)
def get_ultimo(url):
    response = requests.get(
        url,
        timeout=12,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    response.raise_for_status()
    data = response.json()
    dezenas = to_nums(data.get("listaDezenas"))
    if not dezenas:
        raise ValueError("Resposta inesperada da Caixa")
    segundo = to_nums(data.get("listaDezenasSegundoSorteio"))
    estimado = data.get("valorEstimadoProximoConcurso")
    faixas = []
    for faixa in data.get("listaRateioPremio") or []:
        descricao = faixa.get("descricaoFaixa")
        if not descricao:
            continue
        faixas.append(
            {
                "descricao": descricao,
                "ganhadores": int(faixa.get("numeroDeGanhadores") or 0),
                "valor": float(faixa.get("valorPremio") or 0),
            }
        )
        if len(faixas) == 4:
            break
    local = (data.get("nomeMunicipioUFSorteio") or "").strip()
    return {
        "numero": int(data.get("numero")),
        "data": data.get("dataApuracao") or "",
        "proximo": data.get("dataProximoConcurso") or "",
        "dezenas": dezenas,
        "dezenas2": segundo or None,
        "premio": float(estimado) if isinstance(estimado, (int, float)) and estimado > 0 else None,
        "acumulado": bool(data.get("acumulado")),
        "local": local,
        "faixas": faixas,
    }


@st.cache_data(ttl=1800)
def get_hist(url, dois):
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Histórico indisponível")
    counts = Counter()
    for item in data:
        lists = (
            [item.get("resultado_1") or [], item.get("resultado_2") or []]
            if dois
            else [item.get("resultado") or item.get("resultado_1") or []]
        )
        for group in lists:
            for n in to_nums(group):
                counts[n] += 1
    if not counts:
        raise ValueError("Histórico indisponível")
    return dict(counts), len(data)


def weighted_sample(pool, k):
    bag = [{"n": item["n"], "w": max(1, item["w"])} for item in pool]
    picked = []
    take = min(k, len(bag))
    for _ in range(take):
        total = sum(item["w"] for item in bag)
        r = random.random() * total
        idx = len(bag) - 1
        for j, item in enumerate(bag):
            r -= item["w"]
            if r <= 0:
                idx = j
                break
        picked.append(bag[idx]["n"])
        bag.pop(idx)
    picked.sort()
    return picked


def make_games(counts, qtd, qty, universe):
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    pool_size = min(universe, qtd + 12)
    pool = [{"n": n, "w": c} for n, c in ranked[:pool_size]]
    if len(pool) < qtd:
        raise ValueError("Histórico indisponível")
    games = []
    seen = set()
    guard = 0
    while len(games) < qty and guard < 80:
        guard += 1
        game = weighted_sample(pool, qtd)
        key = "-".join(map(str, game))
        if key in seen:
            continue
        seen.add(key)
        games.append(game)
    ranking = [{"n": n, "count": c} for n, c in ranked[:8]]
    return games, ranking


if "loteria" not in st.session_state:
    st.session_state.loteria = "Mega-Sena"
if "sel" not in st.session_state:
    st.session_state.sel = set()
if "intel" not in st.session_state:
    st.session_state.intel = None
if "jogos_salvos" not in st.session_state:
    st.session_state.jogos_salvos = []
if "modo" not in st.session_state:
    st.session_state.modo = "Montar jogo"
if "notice" not in st.session_state:
    st.session_state.notice = ""

loteria = st.session_state.loteria
cfg = LOTERIAS[loteria]
cor = cfg["cor"]

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Outfit:wght@400;500;600;700&display=swap');
:root {{ --accent: {cor}; }}
html, body, [class*="css"] {{ font-family: Outfit, sans-serif; }}
.stApp {{ background: #f3efe6; color: #1a241c; }}
.block-container {{ max-width: 32rem; padding-top: 1.4rem; }}
.marca {{ display: flex; gap: 12px; align-items: center; margin-bottom: 0.8rem; }}
.trevo {{
  width: 48px; height: 48px; border-radius: 16px; background: var(--accent); color: #fffdf8;
  display: flex; align-items: center; justify-content: center; font-size: 1.5rem;
}}
.marca h1 {{
  font-family: "Barlow Condensed", sans-serif; font-size: 2.4rem; line-height: 0.9;
  letter-spacing: 0.04em; margin: 0; font-weight: 700;
}}
.marca p {{ margin: 4px 0 0; color: #445249; font-size: 0.92rem; }}
.ticket {{
  background: #fffdf8; border: 1px solid #e3dacc; border-radius: 18px; overflow: hidden;
  box-shadow: 0 16px 40px -24px rgb(26 36 28 / 0.45); margin: 0.4rem 0 0.8rem;
}}
.ticket-head {{
  background: var(--accent); color: #fffdf8; display: flex; justify-content: space-between;
  align-items: center; gap: 12px; padding: 12px 16px;
}}
.ticket-head h2 {{
  font-family: "Barlow Condensed", sans-serif; font-size: 1.7rem; margin: 0;
  letter-spacing: 0.04em; font-weight: 700;
}}
.chip {{
  background: #fffdf8; color: var(--accent); border-radius: 999px; padding: 4px 10px;
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em;
}}
.ticket-body {{ padding: 16px; }}
.kicker {{ color: #445249; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }}
.premio {{
  font-family: "Barlow Condensed", sans-serif; font-size: 3rem; line-height: 0.95;
  color: var(--accent); font-weight: 700; margin: 4px 0;
}}
.muted {{ color: #445249; font-size: 0.92rem; }}
.rule {{ border-top: 1px dashed #e3dacc; margin: 14px 0; }}
.bolinha {{
  display: inline-flex; width: 44px; height: 44px; border-radius: 50%; color: #fffdf8;
  align-items: center; justify-content: center; font-family: "Barlow Condensed", sans-serif;
  font-weight: 700; font-size: 1.25rem; margin: 0 6px 6px 0;
}}
.faixa {{ display: flex; justify-content: space-between; gap: 12px; font-size: 0.92rem; margin-top: 6px; }}
.faixa span:first-child {{ color: #445249; }}
button, [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"],
[data-testid="baseButton-primary"], [data-testid="baseButton-secondary"] {{
  border-radius: 14px !important; font-weight: 600 !important; min-height: 44px !important;
}}
button[kind="primary"], [data-testid="stBaseButton-primary"] button, [data-testid="baseButton-primary"] {{
  background: var(--accent) !important; border-color: var(--accent) !important; color: #fffdf8 !important;
}}
button[kind="secondary"], [data-testid="stBaseButton-secondary"] button, [data-testid="baseButton-secondary"] {{
  background: #fffdf8 !important; color: #1a241c !important; border: 1px solid #e3dacc !important;
}}
div[data-testid="column"] button {{
  height: 48px !important; min-width: 0 !important; padding: 0 !important;
  font-family: "Barlow Condensed", sans-serif !important; font-size: 1.35rem !important; font-weight: 700 !important;
}}
div[data-testid="stRadio"] label {{ font-weight: 600; }}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="marca">
  <div class="trevo">♣</div>
  <div>
    <h1>Loterias Caixa</h1>
    <p>Resultados oficiais e volante para os seus jogos</p>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

nomes = list(LOTERIAS.keys())
for linha in (nomes[:2], nomes[2:]):
    cols = st.columns(2)
    for col, nome in zip(cols, linha):
        with col:
            tipo = "primary" if nome == loteria else "secondary"
            if st.button(nome, key=f"lot-{nome}", type=tipo, use_container_width=True):
                if nome != loteria:
                    st.session_state.loteria = nome
                    st.session_state.sel = set()
                    st.session_state.intel = None
                    st.rerun()

try:
    concurso = get_ultimo(cfg["api"])
    erro_concurso = None
except Exception:
    concurso = None
    erro_concurso = "Não consegui consultar o último concurso. Tente de novo."

if erro_concurso or not concurso:
    st.markdown(
        f'<div class="ticket"><div class="ticket-body"><h2 style="margin:0">{loteria}</h2>'
        f'<p class="muted">{erro_concurso or "Buscando o último concurso…"}</p></div></div>',
        unsafe_allow_html=True,
    )
else:
    chip = "ACUMULOU" if concurso["acumulado"] else "TEVE GANHADOR"
    premio_html = ""
    if concurso["premio"]:
        digits = 0 if float(concurso["premio"]).is_integer() else 2
        quando = (
            f"Próximo concurso em {concurso['proximo']}"
            if concurso["proximo"]
            else "Próximo concurso"
        )
        premio_html = (
            f'<p class="kicker">Prêmio estimado</p>'
            f'<p class="premio">{brl(concurso["premio"], digits)}</p>'
            f'<p class="muted">{quando}</p>'
        )
    sorteios = ""
    if concurso["dezenas2"]:
        sorteios += '<p class="kicker">1º sorteio</p>'
    sorteios += balls(concurso["dezenas"], cor)
    if concurso["dezenas2"]:
        sorteios += '<p class="kicker" style="margin-top:12px">2º sorteio</p>'
        sorteios += balls(concurso["dezenas2"], cor)
    faixas_html = ""
    for faixa in concurso["faixas"]:
        direita = (
            "Nenhum"
            if faixa["ganhadores"] == 0
            else f'{faixa["ganhadores"]:,}'.replace(",", ".") + f' · {brl(faixa["valor"], 2)}'
        )
        faixas_html += (
            f'<div class="faixa"><span>{faixa["descricao"]}</span><span>{direita}</span></div>'
        )
    local = f'<p class="kicker">{concurso["local"]}</p>' if concurso["local"] else ""
    data = f' · {concurso["data"]}' if concurso["data"] else ""
    st.markdown(
        f"""
<div class="ticket">
  <div class="ticket-head"><h2>{loteria}</h2><span class="chip">{chip}</span></div>
  <div class="ticket-body">
    {premio_html}
    <div class="rule"></div>
    <p style="font-weight:600;margin:0 0 4px">Concurso {concurso["numero"]}<span class="muted">{data}</span></p>
    {local}
    <div style="margin-top:10px">{sorteios}</div>
    <div style="margin-top:10px">{faixas_html}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

if st.button("Atualizar", use_container_width=True):
    get_ultimo.clear()
    st.rerun()

st.session_state.modo = st.radio(
    "Modo",
    ["Montar jogo", "Inteligente"],
    horizontal=True,
    index=0 if st.session_state.modo == "Montar jogo" else 1,
    label_visibility="collapsed",
)

if st.session_state.modo == "Montar jogo":
    universo = list(range(cfg["min"], cfg["max"] + 1))
    st.markdown("### Volante")
    st.markdown(
        f'**{len(st.session_state.sel)}/{cfg["qtd"]}** · escolha {cfg["qtd"]} números de {cfg["min"]:02d} a {cfg["max"]:02d}.'
    )
    for i in range(0, len(universo), 5):
        cols = st.columns(5)
        for col, num in zip(cols, universo[i : i + 5]):
            with col:
                selected = num in st.session_state.sel
                disabled = (not selected) and len(st.session_state.sel) >= cfg["qtd"]
                if st.button(
                    f"{num:02d}",
                    key=f"n-{loteria}-{num}",
                    type="primary" if selected else "secondary",
                    disabled=disabled,
                    use_container_width=True,
                ):
                    if selected:
                        st.session_state.sel.discard(num)
                    elif len(st.session_state.sel) < cfg["qtd"]:
                        st.session_state.sel.add(num)
                    st.rerun()

    c1, c2 = st.columns(2)
    fechado = len(st.session_state.sel) == cfg["qtd"]
    with c1:
        rotulo = "Surpresinha" if not st.session_state.sel else "Completar"
        if st.button(rotulo, disabled=fechado, use_container_width=True):
            faltam = cfg["qtd"] - len(st.session_state.sel)
            livres = [n for n in universo if n not in st.session_state.sel]
            st.session_state.sel.update(random.sample(livres, min(faltam, len(livres))))
            st.rerun()
    with c2:
        if st.button("Limpar", disabled=not st.session_state.sel, use_container_width=True):
            st.session_state.sel = set()
            st.rerun()

    if fechado:
        jogo = sorted(st.session_state.sel)
        st.markdown(
            f'<p style="color:{cor};font-weight:700;margin-bottom:6px">Jogo fechado</p>' + balls(jogo, cor),
            unsafe_allow_html=True,
        )
        if concurso:
            h1 = hits(jogo, concurso["dezenas"])
            if concurso["dezenas2"]:
                h2 = hits(jogo, concurso["dezenas2"])
                texto = f'{hit_phrase(h1, "no 1º")} · {hit_phrase(h2, "no 2º")}'
                premio = h1 >= cfg["premio_min"] or h2 >= cfg["premio_min"]
            else:
                texto = hit_phrase(h1, f'no concurso {concurso["numero"]}')
                premio = h1 >= cfg["premio_min"]
            cor_texto = cor if premio else "#445249"
            st.markdown(f'<p style="color:{cor_texto}">{texto}</p>', unsafe_allow_html=True)
        if st.button("Salvar jogo", type="primary", use_container_width=True):
            chave = (loteria, tuple(jogo))
            if any((j["loteria"], tuple(j["numeros"])) == chave for j in st.session_state.jogos_salvos):
                st.session_state.notice = "Esse jogo já está salvo"
            else:
                st.session_state.jogos_salvos.insert(
                    0, {"loteria": loteria, "numeros": jogo, "modo": "Manual"}
                )
                st.session_state.jogos_salvos = st.session_state.jogos_salvos[:40]
                st.session_state.sel = set()
                st.session_state.notice = "Jogo salvo nesta sessão"
            st.rerun()
else:
    st.markdown("### Formulação inteligente")
    st.caption(
        "Monta jogos dando mais peso aos números que mais saíram no histórico. "
        "Cada combinação continua igualmente possível — isso não aumenta a chance de ganhar."
    )
    qtd = st.slider("Quantidade de jogos", 1, 8, 3)
    if st.button("Gerar jogos", type="primary", use_container_width=True):
        with st.spinner("Analisando histórico…"):
            try:
                counts, concursos = get_hist(cfg["json"], cfg["dois"])
                games, ranking = make_games(
                    counts, cfg["qtd"], qtd, cfg["max"] - cfg["min"] + 1
                )
                st.session_state.intel = {
                    "loteria": loteria,
                    "games": games,
                    "ranking": ranking,
                    "concursos": concursos,
                }
                st.session_state.notice = ""
            except Exception:
                st.session_state.intel = None
                st.error("Não consegui carregar o histórico para formular os jogos.")
    intel = st.session_state.intel
    if intel and intel.get("loteria") == loteria:
        rank_html = "".join(
            f'<span style="display:inline-flex;flex-direction:column;align-items:center;margin:0 8px 8px 0">'
            f'<span class="bolinha" style="background:{cor};margin:0">{r["n"]:02d}</span>'
            f'<span class="muted">{r["count"]}</span></span>'
            for r in intel["ranking"]
        )
        st.markdown(
            f'<p class="kicker">Mais sorteados em {intel["concursos"]:,} concursos</p>'.replace(",", ".")
            + rank_html,
            unsafe_allow_html=True,
        )
        for i, jogo in enumerate(intel["games"], 1):
            st.markdown(f"**Jogo {i}**")
            st.markdown(balls(jogo, cor), unsafe_allow_html=True)
            if st.button("Salvar", key=f"s-{loteria}-{i}"):
                chave = (loteria, tuple(jogo))
                if any((j["loteria"], tuple(j["numeros"])) == chave for j in st.session_state.jogos_salvos):
                    st.session_state.notice = "Esse jogo já está salvo"
                else:
                    st.session_state.jogos_salvos.insert(
                        0, {"loteria": loteria, "numeros": jogo, "modo": "Inteligente"}
                    )
                    st.session_state.jogos_salvos = st.session_state.jogos_salvos[:40]
                    st.session_state.notice = "Jogo salvo nesta sessão"
                st.rerun()

st.markdown("---")
st.markdown(f"### Jogos salvos · {len(st.session_state.jogos_salvos)}")
if st.session_state.notice:
    st.success(st.session_state.notice)
if not st.session_state.jogos_salvos:
    st.caption("Nenhum jogo salvo ainda. Monte um volante ou gere uma formulação e toque em salvar.")
else:
    for idx, jogo in enumerate(list(st.session_state.jogos_salvos)):
        meta = LOTERIAS[jogo["loteria"]]
        st.markdown(f'**{jogo["loteria"]}** · {jogo["modo"]}')
        st.markdown(balls(jogo["numeros"], meta["cor"]), unsafe_allow_html=True)
        if concurso and jogo["loteria"] == loteria:
            h1 = hits(jogo["numeros"], concurso["dezenas"])
            if concurso["dezenas2"]:
                h2 = hits(jogo["numeros"], concurso["dezenas2"])
                texto = f'{hit_phrase(h1, "no 1º")} · {hit_phrase(h2, "no 2º")}'
            else:
                texto = hit_phrase(h1, f'no concurso {concurso["numero"]}')
            st.caption(texto)
        a, b = st.columns(2)
        with a:
            if st.button("Copiar", key=f"copy-{idx}", use_container_width=True):
                texto = " ".join(f"{n:02d}" for n in jogo["numeros"])
                st.session_state.notice = texto
                st.code(texto, language=None)
        with b:
            if st.button("Apagar", key=f"del-{idx}", use_container_width=True):
                st.session_state.jogos_salvos.pop(idx)
                st.rerun()

st.caption(
    "Jogue com responsabilidade. Este app não vende apostas e não tem vínculo com a Caixa Econômica Federal. "
    "Os jogos salvos duram só enquanto esta sessão estiver aberta."
  )
