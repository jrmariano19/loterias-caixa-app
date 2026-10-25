import math
import random

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


def _mean_std(values):
    count = len(values)
    if count == 0:
        return 0.0, 1.0
    mean = sum(values) / count
    var = sum((value - mean) ** 2 for value in values) / count
    std = math.sqrt(var)
    return mean, std if std > 1e-9 else 1.0


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


@st.cache_data(ttl=1800)
def get_hist(url, dois, min_n, max_n):
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Histórico indisponível")
    data = sorted(data, key=lambda item: item.get("concurso") or 0)
    draws = []
    for item in data:
        groups = (
            [item.get("resultado_1") or [], item.get("resultado_2") or []]
            if dois
            else [item.get("resultado") or item.get("resultado_1") or []]
        )
        for group in groups:
            nums = [n for n in to_nums(group) if min_n <= n <= max_n]
            if nums:
                draws.append(nums)
    if len(draws) < 30:
        raise ValueError("Histórico indisponível")
    return draws, len(data)


def _analyze(draws, min_n, max_n, qtd):
    universe = list(range(min_n, max_n + 1))
    mid = (min_n + max_n) / 2
    freq = {n: 0 for n in universe}
    last = {n: -1 for n in universe}
    gap_sum = {n: 0 for n in universe}
    gap_count = {n: 0 for n in universe}
    sums, evens, lows, consecutives = [], [], [], []
    clean = []
    for draw in draws:
        nums = sorted({n for n in draw if min_n <= n <= max_n})
        if len(nums) < qtd:
            continue
        clean.append(nums)
    if len(clean) < 30:
        raise ValueError("Histórico indisponível")
    for index, nums in enumerate(clean):
        for n in nums:
            if last[n] >= 0:
                gap_sum[n] += index - last[n]
                gap_count[n] += 1
            last[n] = index
            freq[n] += 1
        sums.append(sum(nums))
        evens.append(sum(1 for n in nums if n % 2 == 0))
        lows.append(sum(1 for n in nums if n <= mid))
        consecutives.append(sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1))
    total = len(clean)
    window = min(40, total)
    recent = {n: 0 for n in universe}
    for nums in clean[-window:]:
        for n in nums:
            recent[n] += 1
    mean_freq, std_freq = _mean_std([freq[n] for n in universe])
    mean_recent, std_recent = _mean_std([recent[n] for n in universe])
    expected_gap = (max_n - min_n + 1) / qtd
    current_gap = {}
    ratios = []
    for n in universe:
        current_gap[n] = (total - 1 - last[n]) if last[n] >= 0 else total
        average = (gap_sum[n] / gap_count[n]) if gap_count[n] else expected_gap
        ratios.append(current_gap[n] / average if average else 0)
    mean_ratio, std_ratio = _mean_std(ratios)
    scores = {}
    for index, n in enumerate(universe):
        z_freq = (freq[n] - mean_freq) / std_freq
        z_recent = (recent[n] - mean_recent) / std_recent
        z_gap = (ratios[index] - mean_ratio) / std_ratio
        scores[n] = 0.45 * z_freq + 0.35 * z_recent + 0.20 * z_gap
    raw = list(scores.values())
    low_score, high_score = min(raw), max(raw)
    span = high_score - low_score or 1
    ranking = []
    for n in universe:
        ranking.append(
            {
                "n": n,
                "count": freq[n],
                "atraso": current_gap[n],
                "pontos": round(100 * (scores[n] - low_score) / span),
                "score": scores[n],
            }
        )
    ranking.sort(key=lambda item: (-item["score"], item["n"]))
    sorted_sums = sorted(sums)
    profile = {
        "soma_min": int(round(_percentile(sorted_sums, 0.25))),
        "soma_max": int(round(_percentile(sorted_sums, 0.75))),
        "pares": int(round(sum(evens) / len(evens))),
        "baixos": int(round(sum(lows) / len(lows))),
        "max_consec": max(1, int(round(_percentile(sorted(consecutives), 0.75)))),
        "span_min": _percentile(sorted(nums[-1] - nums[0] for nums in clean), 0.15),
        "span_max": _percentile(sorted(nums[-1] - nums[0] for nums in clean), 0.90),
        "janela": window,
        "mid": mid,
    }
    return scores, ranking, profile


def _weights(scores, used):
    adjusted = {n: score - 0.45 * used.get(n, 0) for n, score in scores.items()}
    top = max(adjusted.values())
    return {n: math.exp((score - top) / 1.15) for n, score in adjusted.items()}


def _sample(weights, k):
    bag = [{"n": n, "w": w} for n, w in weights.items()]
    picked = []
    for _ in range(min(k, len(bag))):
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


def _fits(game, profile, level):
    total = sum(game)
    width = max(1, profile["soma_max"] - profile["soma_min"])
    pad = 0 if level == 0 else width * (0.2 if level == 1 else 0.6)
    if not (profile["soma_min"] - pad <= total <= profile["soma_max"] + pad):
        return False
    slack = 1 if level == 0 else 2 if level == 1 else 4
    pares = sum(1 for n in game if n % 2 == 0)
    if abs(pares - profile["pares"]) > slack:
        return False
    baixos = sum(1 for n in game if n <= profile["mid"])
    if abs(baixos - profile["baixos"]) > slack:
        return False
    sequencias = sum(1 for a, b in zip(game, game[1:]) if b == a + 1)
    limit = profile["max_consec"] if level == 0 else profile["max_consec"] + (2 if level == 1 else 99)
    if sequencias > limit:
        return False
    span = game[-1] - game[0]
    span_pad = 0 if level == 0 else 4 if level == 1 else 99
    if span < profile["span_min"] - span_pad or span > profile["span_max"] + span_pad:
        return False
    return True


def make_games(draws, min_n, max_n, qtd, qty):
    scores, ranking, profile = _analyze(draws, min_n, max_n, qtd)
    games = []
    seen = set()
    used = {}
    for level in (0, 1, 2):
        guard = 0
        while len(games) < qty and guard < 80:
            guard += 1
            game = _sample(_weights(scores, used), qtd)
            key = "-".join(map(str, game))
            if key in seen or not _fits(game, profile, level):
                continue
            seen.add(key)
            games.append(game)
            for n in game:
                used[n] = used.get(n, 0) + 1
        if len(games) >= qty:
            break
    guard = 0
    while len(games) < qty and guard < 40:
        guard += 1
        game = _sample(_weights(scores, used), qtd)
        key = "-".join(map(str, game))
        if key in seen:
            continue
        seen.add(key)
        games.append(game)
        for n in game:
            used[n] = used.get(n, 0) + 1
    return games, ranking[:8], profile


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
        "Cada número recebe uma pontuação calculada nos concursos anteriores: "
        "45% pela frequência em todo o histórico, 35% pela frequência nos últimos 40 concursos "
        "e 20% pelo atraso (quantos sorteios está sem sair, comparado com a média dele). "
        "O jogo é fechado no perfil dos resultados reais: soma, pares, números baixos e sequências. "
        "Isso descreve o passado. Não aumenta a chance de ganhar."
    )
    qtd = st.slider("Quantidade de jogos", 1, 8, 3)
    if st.button("Gerar jogos", type="primary", use_container_width=True):
        with st.spinner("Analisando histórico…"):
            try:
                draws, concursos = get_hist(cfg["json"], cfg["dois"], cfg["min"], cfg["max"])
                games, ranking, profile = make_games(
                    draws, cfg["min"], cfg["max"], cfg["qtd"], qtd
                )
                st.session_state.intel = {
                    "loteria": loteria,
                    "games": games,
                    "ranking": ranking,
                    "concursos": concursos,
                    "profile": profile,
                }
                st.session_state.notice = ""
            except Exception:
                st.session_state.intel = None
                st.error("Não consegui carregar o histórico para formular os jogos.")
    intel = st.session_state.intel
    if intel and intel.get("loteria") == loteria:
        perfil = intel["profile"]
        st.markdown(
            f'<p class="kicker">{intel["concursos"]:,} concursos · soma típica {perfil["soma_min"]}–{perfil["soma_max"]} · cerca de {perfil["pares"]} pares</p>'.replace(
                ",", "."
            ),
            unsafe_allow_html=True,
        )
        rank_html = "".join(
            f'<span style="display:inline-flex;flex-direction:column;align-items:center;margin:0 8px 8px 0">'
            f'<span class="bolinha" style="background:{cor};margin:0">{r["n"]:02d}</span>'
            f'<span class="muted">{r["pontos"]} pts</span>'
            f'<span class="muted">{r["atraso"]} atr.</span></span>'
            for r in intel["ranking"]
        )
        st.markdown('<p class="kicker">Maior pontuação</p>' + rank_html, unsafe_allow_html=True)
        for i, jogo in enumerate(intel["games"], 1):
            pares = sum(1 for n in jogo if n % 2 == 0)
            st.markdown(f"**Jogo {i}**")
            st.markdown(balls(jogo, cor), unsafe_allow_html=True)
            st.caption(f"Soma {sum(jogo)} · {pares} pares")
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
