export const LOTERIAS = {
  megasena: {
    nome: "Mega-Sena",
    api: "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/",
    json: "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/mega-sena.json",
    min: 1,
    max: 60,
    qtd: 6,
    premioMin: 4,
    tone: "mega",
    doisSorteios: false,
  },
  lotofacil: {
    nome: "Lotofácil",
    api: "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/",
    json: "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotofacil.json",
    min: 1,
    max: 25,
    qtd: 15,
    premioMin: 11,
    tone: "loto",
    doisSorteios: false,
  },
  quina: {
    nome: "Quina",
    api: "https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/",
    json: "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/quina.json",
    min: 1,
    max: 80,
    qtd: 5,
    premioMin: 2,
    tone: "quina",
    doisSorteios: false,
  },
  duplasena: {
    nome: "Dupla Sena",
    api: "https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena/",
    json: "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/dupla-sena.json",
    min: 1,
    max: 50,
    qtd: 6,
    premioMin: 3,
    tone: "dupla",
    doisSorteios: true,
  },
} as const;

export type LotteryId = keyof typeof LOTERIAS;
export type LotteryTone = (typeof LOTERIAS)[LotteryId]["tone"];

export const LOTTERY_IDS = Object.keys(LOTERIAS) as LotteryId[];

export type Faixa = {
  descricao: string;
  ganhadores: number;
  valor: number;
};

export type LatestDraw = {
  id: LotteryId;
  numero: number;
  dataApuracao: string;
  dataProximo: string | null;
  dezenas: number[];
  dezenas2: number[] | null;
  premioEstimado: number | null;
  acumulado: boolean;
  local: string | null;
  faixas: Faixa[];
};

export type RankedNumber = { n: number; count: number; pontos: number; atraso: number };

export type SmartProfile = {
  somaMin: number;
  somaMax: number;
  pares: number;
  janela: number;
};

export type SmartResult = {
  games: number[][];
  ranking: RankedNumber[];
  concursos: number;
  profile: SmartProfile;
};

export type SavedGame = {
  id: string;
  loteria: LotteryId;
  numeros: number[];
  modo: "Manual" | "Inteligente";
};

export const STORAGE_KEY = "loterias-caixa-v1";

export function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function formatBRL(value: number, digits: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function numbersOf(id: LotteryId): number[] {
  const { min, max } = LOTERIAS[id];
  const out: number[] = [];
  for (let n = min; n <= max; n += 1) out.push(n);
  return out;
}

export function countHits(game: number[], draw: number[]): number {
  const set = new Set(draw);
  let hits = 0;
  for (const n of game) if (set.has(n)) hits += 1;
  return hits;
}

export function gameKey(nums: number[]): string {
  return [...nums].sort((a, b) => a - b).join("-");
  }
