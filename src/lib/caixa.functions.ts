import { createServerFn } from "@tanstack/react-start";
import {
  LOTERIAS,
  type Faixa,
  type LatestDraw,
  type LotteryId,
  type SmartResult,
} from "@/lib/loterias";

const LATEST_TTL = 60_000;
const HIST_TTL = 30 * 60_000;

const latestCache = new Map<LotteryId, { at: number; data: LatestDraw }>();
const histCache = new Map<LotteryId, { at: number; draws: number[][]; concursos: number }>();

function parseId(input: unknown): LotteryId {
  const rec = typeof input === "object" && input !== null ? (input as Record<string, unknown>) : {};
  const id = rec.id;
  if (typeof id !== "string" || !(id in LOTERIAS)) throw new Error("Loteria inválida");
  return id as LotteryId;
}

function toNums(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  const nums: number[] = [];
  for (const item of value) {
    const n = typeof item === "number" ? item : Number.parseInt(String(item), 10);
    if (Number.isInteger(n)) nums.push(n);
  }
  nums.sort((a, b) => a - b);
  return nums;
}

function toFaixas(value: unknown): Faixa[] {
  if (!Array.isArray(value)) return [];
  const out: Faixa[] = [];
  for (const item of value) {
    if (typeof item !== "object" || item === null) continue;
    const rec = item as Record<string, unknown>;
    const descricao = typeof rec.descricaoFaixa === "string" ? rec.descricaoFaixa : "";
    if (!descricao) continue;
    out.push({
      descricao,
      ganhadores: typeof rec.numeroDeGanhadores === "number" ? rec.numeroDeGanhadores : 0,
      valor: typeof rec.valorPremio === "number" ? rec.valorPremio : 0,
    });
    if (out.length === 4) break;
  }
  return out;
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, {
    headers: { accept: "application/json", "user-agent": "Mozilla/5.0" },
    signal: AbortSignal.timeout(12_000),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function readLatest(id: LotteryId, payload: unknown): LatestDraw {
  if (typeof payload !== "object" || payload === null) {
    throw new Error("Resposta inesperada da Caixa");
  }
  const rec = payload as Record<string, unknown>;
  const numero = typeof rec.numero === "number" ? rec.numero : Number(rec.numero);
  const dezenas = toNums(rec.listaDezenas);
  if (!Number.isFinite(numero) || dezenas.length === 0) {
    throw new Error("Resposta inesperada da Caixa");
  }
  const segundo = toNums(rec.listaDezenasSegundoSorteio);
  const estimado = rec.valorEstimadoProximoConcurso;
  const localRaw = typeof rec.nomeMunicipioUFSorteio === "string" ? rec.nomeMunicipioUFSorteio.trim() : "";
  const proximo = typeof rec.dataProximoConcurso === "string" ? rec.dataProximoConcurso : "";
  return {
    id,
    numero,
    dataApuracao: typeof rec.dataApuracao === "string" ? rec.dataApuracao : "",
    dataProximo: proximo || null,
    dezenas,
    dezenas2: segundo.length > 0 ? segundo : null,
    premioEstimado: typeof estimado === "number" && estimado > 0 ? estimado : null,
    acumulado: rec.acumulado === true,
    local: localRaw || null,
    faixas: toFaixas(rec.listaRateioPremio),
  };
}

async function historyDraws(id: LotteryId): Promise<{ draws: number[][]; concursos: number }> {
  const hit = histCache.get(id);
  if (hit && Date.now() - hit.at < HIST_TTL) return hit;
  const response = await fetch(LOTERIAS[id].json, {
    headers: { accept: "application/json", "user-agent": "Mozilla/5.0" },
    signal: AbortSignal.timeout(20_000),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const payload: unknown = await response.json();
  if (!Array.isArray(payload) || payload.length === 0) throw new Error("Histórico indisponível");
  const rows = payload.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null);
  rows.sort((a, b) => Number(a.concurso ?? 0) - Number(b.concurso ?? 0));
  const cfg = LOTERIAS[id];
  const draws: number[][] = [];
  for (const rec of rows) {
    const groups = cfg.doisSorteios ? [rec.resultado_1, rec.resultado_2] : [rec.resultado ?? rec.resultado_1];
    for (const group of groups) {
      const nums = toNums(group).filter((n) => n >= cfg.min && n <= cfg.max);
      if (nums.length > 0) draws.push(nums);
    }
  }
  if (draws.length < 30) throw new Error("Histórico indisponível");
  const data = { draws, concursos: rows.length, at: Date.now() };
  histCache.set(id, data);
  return data;
}

function meanStd(values: number[]): { mean: number; std: number } {
  if (values.length === 0) return { mean: 0, std: 1 };
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  const std = Math.sqrt(variance);
  return { mean, std: std > 1e-9 ? std : 1 };
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  const k = (sorted.length - 1) * p;
  const lo = Math.floor(k);
  const hi = Math.min(lo + 1, sorted.length - 1);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (k - lo);
}

type Profile = {
  somaMin: number;
  somaMax: number;
  pares: number;
  baixos: number;
  maxConsec: number;
  spanMin: number;
  spanMax: number;
  janela: number;
  mid: number;
};

function analyze(draws: number[][], min: number, max: number, qtd: number) {
  const universe: number[] = [];
  for (let n = min; n <= max; n += 1) universe.push(n);
  const mid = (min + max) / 2;
  const freq = new Map<number, number>();
  const last = new Map<number, number>();
  const gapSum = new Map<number, number>();
  const gapCount = new Map<number, number>();
  for (const n of universe) {
    freq.set(n, 0);
    last.set(n, -1);
    gapSum.set(n, 0);
    gapCount.set(n, 0);
  }
  const clean = draws
    .map((draw) => [...new Set(draw.filter((n) => n >= min && n <= max))].sort((a, b) => a - b))
    .filter((nums) => nums.length >= qtd);
  if (clean.length < 30) throw new Error("Histórico indisponível");
  const sums: number[] = [];
  const evens: number[] = [];
  const lows: number[] = [];
  const consecutives: number[] = [];
  clean.forEach((nums, index) => {
    for (const n of nums) {
      const seen = last.get(n) ?? -1;
      if (seen >= 0) {
        gapSum.set(n, (gapSum.get(n) ?? 0) + (index - seen));
        gapCount.set(n, (gapCount.get(n) ?? 0) + 1);
      }
      last.set(n, index);
      freq.set(n, (freq.get(n) ?? 0) + 1);
    }
    sums.push(nums.reduce((sum, n) => sum + n, 0));
    evens.push(nums.filter((n) => n % 2 === 0).length);
    lows.push(nums.filter((n) => n <= mid).length);
    consecutives.push(nums.filter((n, i) => i > 0 && n === nums[i - 1] + 1).length);
  });
  const total = clean.length;
  const window = Math.min(40, total);
  const recent = new Map<number, number>();
  for (const n of universe) recent.set(n, 0);
  for (const nums of clean.slice(-window)) {
    for (const n of nums) recent.set(n, (recent.get(n) ?? 0) + 1);
  }
  const freqStats = meanStd(universe.map((n) => freq.get(n) ?? 0));
  const recentStats = meanStd(universe.map((n) => recent.get(n) ?? 0));
  const expectedGap = (max - min + 1) / qtd;
  const currentGap = new Map<number, number>();
  const ratios = universe.map((n) => {
    const seen = last.get(n) ?? -1;
    const gap = seen >= 0 ? total - 1 - seen : total;
    currentGap.set(n, gap);
    const count = gapCount.get(n) ?? 0;
    const average = count ? (gapSum.get(n) ?? 0) / count : expectedGap;
    return average ? gap / average : 0;
  });
  const ratioStats = meanStd(ratios);
  const scores = new Map<number, number>();
  universe.forEach((n, index) => {
    const zFreq = ((freq.get(n) ?? 0) - freqStats.mean) / freqStats.std;
    const zRecent = ((recent.get(n) ?? 0) - recentStats.mean) / recentStats.std;
    const zGap = (ratios[index] - ratioStats.mean) / ratioStats.std;
    scores.set(n, 0.45 * zFreq + 0.35 * zRecent + 0.2 * zGap);
  });
  const raw = [...scores.values()];
  const lowScore = Math.min(...raw);
  const highScore = Math.max(...raw);
  const span = highScore - lowScore || 1;
  const ranking = universe
    .map((n) => ({
      n,
      count: freq.get(n) ?? 0,
      atraso: currentGap.get(n) ?? total,
      pontos: Math.round((100 * ((scores.get(n) ?? 0) - lowScore)) / span),
      score: scores.get(n) ?? 0,
    }))
    .sort((a, b) => b.score - a.score || a.n - b.n);
  const sortedSums = [...sums].sort((a, b) => a - b);
  const spans = clean.map((nums) => nums[nums.length - 1] - nums[0]).sort((a, b) => a - b);
  const profile: Profile = {
    somaMin: Math.round(percentile(sortedSums, 0.25)),
    somaMax: Math.round(percentile(sortedSums, 0.75)),
    pares: Math.round(evens.reduce((sum, n) => sum + n, 0) / evens.length),
    baixos: Math.round(lows.reduce((sum, n) => sum + n, 0) / lows.length),
    maxConsec: Math.max(1, Math.round(percentile([...consecutives].sort((a, b) => a - b), 0.75))),
    spanMin: percentile(spans, 0.15),
    spanMax: percentile(spans, 0.9),
    janela: window,
    mid,
  };
  return { scores, ranking, profile };
}

function sampleWeighted(weights: Map<number, number>, k: number): number[] {
  const bag = [...weights.entries()].map(([n, w]) => ({ n, w }));
  const picked: number[] = [];
  const take = Math.min(k, bag.length);
  for (let i = 0; i < take; i += 1) {
    let total = 0;
    for (const item of bag) total += item.w;
    let r = Math.random() * total;
    let idx = bag.length - 1;
    for (let j = 0; j < bag.length; j += 1) {
      r -= bag[j].w;
      if (r <= 0) {
        idx = j;
        break;
      }
    }
    picked.push(bag[idx].n);
    bag.splice(idx, 1);
  }
  picked.sort((a, b) => a - b);
  return picked;
}

function weightsFor(scores: Map<number, number>, used: Map<number, number>): Map<number, number> {
  let top = -Infinity;
  const adjusted = new Map<number, number>();
  for (const [n, score] of scores) {
    const value = score - 0.45 * (used.get(n) ?? 0);
    adjusted.set(n, value);
    if (value > top) top = value;
  }
  const weights = new Map<number, number>();
  for (const [n, score] of adjusted) weights.set(n, Math.exp((score - top) / 1.15));
  return weights;
}

function fits(game: number[], profile: Profile, level: number): boolean {
  const total = game.reduce((sum, n) => sum + n, 0);
  const width = Math.max(1, profile.somaMax - profile.somaMin);
  const pad = level === 0 ? 0 : width * (level === 1 ? 0.2 : 0.6);
  if (total < profile.somaMin - pad || total > profile.somaMax + pad) return false;
  const slack = level === 0 ? 1 : level === 1 ? 2 : 4;
  const pares = game.filter((n) => n % 2 === 0).length;
  if (Math.abs(pares - profile.pares) > slack) return false;
  const baixos = game.filter((n) => n <= profile.mid).length;
  if (Math.abs(baixos - profile.baixos) > slack) return false;
  const sequencias = game.filter((n, i) => i > 0 && n === game[i - 1] + 1).length;
  const limit = profile.maxConsec + (level === 0 ? 0 : level === 1 ? 2 : 99);
  if (sequencias > limit) return false;
  const span = game[game.length - 1] - game[0];
  const spanPad = level === 0 ? 0 : level === 1 ? 4 : 99;
  if (span < profile.spanMin - spanPad || span > profile.spanMax + spanPad) return false;
  return true;
}

export const getLatest = createServerFn({ method: "GET" })
  .validator((input: unknown): { id: LotteryId; fresh: boolean } => {
    const rec = typeof input === "object" && input !== null ? (input as Record<string, unknown>) : {};
    return { id: parseId(input), fresh: rec.fresh === true };
  })
  .handler(async ({ data }): Promise<LatestDraw> => {
    try {
      const cached = latestCache.get(data.id);
      if (!data.fresh && cached && Date.now() - cached.at < LATEST_TTL) return cached.data;
      const payload = await fetchJson(LOTERIAS[data.id].api);
      const draw = readLatest(data.id, payload);
      latestCache.set(data.id, { at: Date.now(), data: draw });
      return draw;
    } catch (err) {
      console.error("latest draw", err);
      if (err instanceof Error && /inesperada|inválida/i.test(err.message)) throw err;
      throw new Error("Não consegui consultar o último concurso. Tente de novo.");
    }
  });

export const getSmartGames = createServerFn({ method: "POST" })
  .validator((input: unknown): { id: LotteryId; qty: number } => {
    const id = parseId(input);
    const rec = typeof input === "object" && input !== null ? (input as Record<string, unknown>) : {};
    const qty = typeof rec.qty === "number" ? rec.qty : Number(rec.qty);
    if (!Number.isInteger(qty) || qty < 1 || qty > 8) throw new Error("Quantidade inválida");
    return { id, qty };
  })
  .handler(async ({ data }): Promise<SmartResult> => {
    try {
      const cfg = LOTERIAS[data.id];
      const { draws, concursos } = await historyDraws(data.id);
      const { scores, ranking, profile } = analyze(draws, cfg.min, cfg.max, cfg.qtd);
      const games: number[][] = [];
      const seen = new Set<string>();
      const used = new Map<number, number>();
      for (const level of [0, 1, 2]) {
        let guard = 0;
        while (games.length < data.qty && guard < 80) {
          guard += 1;
          const game = sampleWeighted(weightsFor(scores, used), cfg.qtd);
          const key = game.join("-");
          if (seen.has(key) || !fits(game, profile, level)) continue;
          seen.add(key);
          games.push(game);
          for (const n of game) used.set(n, (used.get(n) ?? 0) + 1);
        }
        if (games.length >= data.qty) break;
      }
      let guard = 0;
      while (games.length < data.qty && guard < 40) {
        guard += 1;
        const game = sampleWeighted(weightsFor(scores, used), cfg.qtd);
        const key = game.join("-");
        if (seen.has(key)) continue;
        seen.add(key);
        games.push(game);
        for (const n of game) used.set(n, (used.get(n) ?? 0) + 1);
      }
      return {
        games,
        ranking: ranking.slice(0, 8).map(({ n, count, pontos, atraso }) => ({ n, count, pontos, atraso })),
        concursos,
        profile: {
          somaMin: profile.somaMin,
          somaMax: profile.somaMax,
          pares: profile.pares,
          janela: profile.janela,
        },
      };
    } catch (err) {
      console.error("smart games", err);
      if (err instanceof Error && /indisponível|inválida/i.test(err.message)) throw err;
      throw new Error("Não consegui carregar o histórico para formular os jogos.");
    }
  });
