import { LOTERIAS, type Faixa, type LatestDraw, type LotteryId } from "@/lib/loterias";

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

export function drawFromCaixa(id: LotteryId, payload: unknown): LatestDraw {
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
  const proximoNumero = Number(rec.numeroConcursoProximo);
  const localRaw = typeof rec.nomeMunicipioUFSorteio === "string" ? rec.nomeMunicipioUFSorteio.trim() : "";
  const proximo = typeof rec.dataProximoConcurso === "string" ? rec.dataProximoConcurso : "";
  return {
    id,
    numero,
    dataApuracao: typeof rec.dataApuracao === "string" ? rec.dataApuracao : "",
    dataProximo: proximo || null,
    concursoAtual: Number.isFinite(proximoNumero) && proximoNumero > numero ? proximoNumero : null,
    dezenas,
    dezenas2: segundo.length > 0 ? segundo : null,
    premioEstimado: typeof estimado === "number" && estimado > 0 ? estimado : null,
    acumulado: rec.acumulado === true,
    local: localRaw || null,
    faixas: toFaixas(rec.listaRateioPremio),
  };
}

async function getJson(url: string): Promise<unknown> {
  const response = await fetch(url, { headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function fetchCaixaLatest(id: LotteryId): Promise<LatestDraw> {
  const base = LOTERIAS[id].api.replace(/\/$/, "");
  const draw = drawFromCaixa(id, await getJson(`${base}/`));
  if (!draw.concursoAtual) return draw;
  try {
    const newer = drawFromCaixa(id, await getJson(`${base}/${draw.concursoAtual}`));
    if (newer.numero > draw.numero && newer.dezenas.length > 0) return newer;
  } catch {
    /* o concurso aberto ainda não foi sorteado */
  }
  return draw;
}
