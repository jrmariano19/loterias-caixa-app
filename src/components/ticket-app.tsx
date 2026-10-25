import { useEffect, useState } from "react";
import { Clover, Copy, Dices, RefreshCw, Shuffle, Sparkles, Trash2 } from "lucide-react";
import { getLatest, getSmartGames } from "@/lib/caixa.functions";
import {
  LOTERIAS,
  LOTTERY_IDS,
  STORAGE_KEY,
  countHits,
  formatBRL,
  gameKey,
  numbersOf,
  pad,
  type LatestDraw,
  type LotteryId,
  type SavedGame,
  type SmartResult,
} from "@/lib/loterias";

const primaryBtn =
  "inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-accent px-4 text-base font-semibold text-card disabled:cursor-default disabled:opacity-50";
const ghostBtn =
  "inline-flex h-12 items-center justify-center gap-2 rounded-2xl border border-line bg-card px-4 text-base font-semibold text-ink disabled:cursor-default disabled:opacity-40";

function isSavedGame(value: unknown): value is SavedGame {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === "string" &&
    typeof v.loteria === "string" &&
    v.loteria in LOTERIAS &&
    Array.isArray(v.numeros) &&
    v.numeros.every((n) => typeof n === "number") &&
    (v.modo === "Manual" || v.modo === "Inteligente")
  );
}

function hitsPhrase(hits: number, where: string): string {
  if (hits === 0) return `Nenhum acerto ${where}`;
  if (hits === 1) return `1 acerto ${where}`;
  return `${hits} acertos ${where}`;
}

function Balls({ numbers }: { numbers: number[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {numbers.map((n) => (
        <span
          key={n}
          className="inline-flex size-11 items-center justify-center rounded-full bg-accent font-display text-xl font-bold leading-none text-card tabular-nums"
        >
          {pad(n)}
        </span>
      ))}
    </div>
  );
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const el = document.createElement("textarea");
    el.value = text;
    el.setAttribute("readonly", "");
    el.style.position = "fixed";
    el.style.left = "-9999px";
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand("copy");
    el.remove();
    if (!ok) throw new Error("copy");
  }
}

export function TicketApp({ initial }: { initial: LatestDraw | null }) {
  const [atual, setAtual] = useState<LotteryId>("megasena");
  const [latest, setLatest] = useState<LatestDraw | null>(initial);
  const [latestError, setLatestError] = useState<string | null>(null);
  const [latestLoading, setLatestLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const [modo, setModo] = useState<"montar" | "inteligente">("montar");
  const [sel, setSel] = useState<number[]>([]);
  const [qty, setQty] = useState(3);
  const [intel, setIntel] = useState<SmartResult | null>(null);
  const [intelError, setIntelError] = useState<string | null>(null);
  const [intelLoading, setIntelLoading] = useState(false);
  const [saved, setSaved] = useState<SavedGame[]>([]);
  const [storageReady, setStorageReady] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const cfg = LOTERIAS[atual];
  const universo = numbersOf(atual);
  const jogo = [...sel].sort((a, b) => a - b);
  const fechado = sel.length === cfg.qtd;
  const show = latest && latest.id === atual ? latest : null;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed: unknown = JSON.parse(raw);
        if (Array.isArray(parsed)) setSaved(parsed.filter(isSavedGame));
      }
    } catch {
      /* storage ilegível */
    }
    setStorageReady(true);
  }, []);

  useEffect(() => {
    if (!storageReady) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  }, [saved, storageReady]);

  useEffect(() => {
    if (!notice) return;
    const t = window.setTimeout(() => setNotice(null), 2200);
    return () => window.clearTimeout(t);
  }, [notice]);

  // `latest` is intentionally omitted: it is only a seed to skip the first fetch.
  useEffect(() => {
    if (tick === 0 && latest?.id === atual) return;
    let alive = true;
    setLatestLoading(true);
    setLatestError(null);
    getLatest({ data: { id: atual, fresh: tick > 0 } })
      .then((data) => {
        if (!alive) return;
        setLatest(data);
        setLatestLoading(false);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setLatest(null);
        setLatestError(err instanceof Error ? err.message : "Não consegui consultar o concurso.");
        setLatestLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atual, tick]);

  function escolher(id: LotteryId) {
    if (id === atual) return;
    setAtual(id);
    setSel([]);
    setIntel(null);
    setIntelError(null);
    setLatest(null);
    setLatestError(null);
  }

  function toggle(n: number) {
    setSel((prev) => {
      if (prev.includes(n)) return prev.filter((x) => x !== n);
      if (prev.length >= cfg.qtd) return prev;
      return [...prev, n];
    });
  }

  function completar() {
    setSel((prev) => {
      const need = cfg.qtd - prev.length;
      if (need <= 0) return prev;
      const pool = universo.filter((n) => !prev.includes(n));
      for (let i = pool.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        const tmp = pool[i];
        pool[i] = pool[j];
        pool[j] = tmp;
      }
      return [...prev, ...pool.slice(0, need)];
    });
  }

  function salvar(numeros: number[], modoJogo: SavedGame["modo"]) {
    const ordenado = [...numeros].sort((a, b) => a - b);
    const key = gameKey(ordenado);
    if (saved.some((g) => g.loteria === atual && gameKey(g.numeros) === key)) {
      setNotice("Esse jogo já está salvo");
      return;
    }
    const jogoSalvo: SavedGame = {
      id: crypto.randomUUID(),
      loteria: atual,
      numeros: ordenado,
      modo: modoJogo,
    };
    setSaved((prev) => [jogoSalvo, ...prev].slice(0, 40));
    if (modoJogo === "Manual") setSel([]);
    setNotice("Jogo salvo neste aparelho");
  }

  async function gerar() {
    setIntelLoading(true);
    setIntelError(null);
    try {
      const data = await getSmartGames({ data: { id: atual, qty } });
      setIntel(data);
    } catch (err) {
      setIntel(null);
      setIntelError(err instanceof Error ? err.message : "Não consegui formular os jogos.");
    } finally {
      setIntelLoading(false);
    }
  }

  async function copiar(nums: number[]) {
    try {
      await copyText(nums.map(pad).join(" "));
      setNotice("Números copiados");
    } catch {
      setNotice("Não foi possível copiar");
    }
  }

  return (
    <div data-loteria={atual} className="mx-auto flex min-h-screen w-full max-w-lg flex-col gap-5 px-4 py-6 sm:py-10">
      <header className="flex items-center gap-3">
        <span className="inline-flex size-12 items-center justify-center rounded-2xl bg-accent text-card">
          <Clover className="size-6" aria-hidden="true" />
        </span>
        <div>
          <h1 className="font-display text-4xl font-bold leading-none tracking-wide">Loterias Caixa</h1>
          <p className="mt-1 text-sm text-muted">Resultados oficiais e volante para os seus jogos</p>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-2" role="group" aria-label="Escolher loteria">
        {LOTTERY_IDS.map((id) => (
          <button
            key={id}
            type="button"
            data-tone={LOTERIAS[id].tone}
            className="tone-btn h-12 rounded-2xl text-sm font-semibold"
            aria-pressed={id === atual}
            onClick={() => escolher(id)}
          >
            {LOTERIAS[id].nome}
          </button>
        ))}
      </div>

      <LatestCard
        nome={cfg.nome}
        draw={show}
        loading={latestLoading && !show}
        refreshing={latestLoading && !!show}
        error={latestError}
        onRetry={() => setTick((t) => t + 1)}
      />

      <div className="grid grid-cols-2 gap-1 rounded-2xl bg-line p-1">
        <button
          type="button"
          aria-pressed={modo === "montar"}
          className={`h-11 rounded-xl text-sm font-semibold ${modo === "montar" ? "bg-card text-ink shadow-ticket" : "text-muted"}`}
          onClick={() => setModo("montar")}
        >
          Montar jogo
        </button>
        <button
          type="button"
          aria-pressed={modo === "inteligente"}
          className={`h-11 rounded-xl text-sm font-semibold ${modo === "inteligente" ? "bg-card text-ink shadow-ticket" : "text-muted"}`}
          onClick={() => setModo("inteligente")}
        >
          Inteligente
        </button>
      </div>

      {modo === "montar" ? (
        <section className="rounded-2xl border border-line bg-card p-4 shadow-ticket">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="text-lg font-semibold">Volante</h2>
            <p className={`font-display text-2xl font-bold tabular-nums ${fechado ? "text-accent" : "text-ink"}`}>
              {sel.length}/{cfg.qtd}
            </p>
          </div>
          <p className="mt-1 text-sm text-muted">
            Escolha {cfg.qtd} números de {pad(cfg.min)} a {pad(cfg.max)}.
          </p>
          <div className="mt-4 grid grid-cols-5 gap-2 sm:grid-cols-8" role="group" aria-label={`Números da ${cfg.nome}`}>
            {universo.map((n) => {
              const on = sel.includes(n);
              const disabled = !on && sel.length >= cfg.qtd;
              return (
                <button
                  key={n}
                  type="button"
                  className={`num-btn h-12 rounded-xl border font-display text-xl font-bold tabular-nums ${
                    on ? "border-accent bg-accent text-card" : "border-line bg-card text-ink"
                  } disabled:opacity-40`}
                  aria-pressed={on}
                  disabled={disabled}
                  onClick={() => toggle(n)}
                >
                  {pad(n)}
                </button>
              );
            })}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <button type="button" className={ghostBtn} onClick={completar} disabled={fechado}>
              {sel.length === 0 ? <Dices className="size-4" aria-hidden="true" /> : <Shuffle className="size-4" aria-hidden="true" />}
              {sel.length === 0 ? "Surpresinha" : "Completar"}
            </button>
            <button type="button" className={ghostBtn} onClick={() => setSel([])} disabled={sel.length === 0}>
              Limpar
            </button>
          </div>
          {fechado ? (
            <div className="mt-4 border-t border-dashed border-line pt-4">
              <p className="text-sm font-semibold text-accent">Jogo fechado</p>
              <div className="mt-3">
                <Balls numbers={jogo} />
              </div>
              {show ? <HitLine game={jogo} draw={show} premioMin={cfg.premioMin} /> : null}
              <button type="button" className={`${primaryBtn} mt-4`} onClick={() => salvar(jogo, "Manual")}>
                Salvar jogo
              </button>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="rounded-2xl border border-line bg-card p-4 shadow-ticket">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-accent" aria-hidden="true" />
            <h2 className="text-lg font-semibold">Formulação inteligente</h2>
          </div>
          <p className="mt-2 text-sm text-muted">
            Cada número recebe uma pontuação calculada nos concursos anteriores: 45% pela frequência em todo o
            histórico, 35% pela frequência nos últimos 40 concursos e 20% pelo atraso (sorteios sem sair, comparado
            com a média dele). O volante fecha no perfil real dos sorteios: soma, pares, números baixos e sequências.
            Isso descreve o passado e não aumenta a chance de ganhar.
          </p>
          <label htmlFor="qtd-jogos" className="mt-4 block">
            <span className="flex items-baseline justify-between">
              <span className="text-sm font-medium">Quantidade de jogos</span>
              <span className="font-display text-3xl font-bold leading-none text-accent tabular-nums">{qty}</span>
            </span>
            <input
              id="qtd-jogos"
              className="mt-3"
              type="range"
              min={1}
              max={8}
              step={1}
              value={qty}
              onChange={(e) => setQty(Number(e.target.value))}
            />
          </label>
          <button type="button" className={`${primaryBtn} mt-4`} onClick={gerar} disabled={intelLoading}>
            {intelLoading ? "Analisando histórico…" : "Gerar jogos"}
          </button>
          {intelError ? <p className="mt-3 text-sm font-medium text-dupla">{intelError}</p> : null}
          {intel ? (
            <div className="mt-5 flex flex-col gap-4">
              <div>
                <p className="text-xs font-semibold tracking-wide text-muted uppercase">
                  {intel.concursos.toLocaleString("pt-BR")} concursos · soma típica {intel.profile.somaMin}–
                  {intel.profile.somaMax} · cerca de {intel.profile.pares} pares
                </p>
                <p className="mt-3 text-xs font-semibold tracking-wide text-muted uppercase">Maior pontuação</p>
                <div className="mt-3 flex flex-wrap gap-3">
                  {intel.ranking.map((r) => (
                    <div key={r.n} className="flex flex-col items-center gap-1">
                      <span className="inline-flex size-10 items-center justify-center rounded-full bg-accent font-display text-lg font-bold text-card tabular-nums">
                        {pad(r.n)}
                      </span>
                      <span className="text-xs text-muted tabular-nums">{r.pontos} pts</span>
                      <span className="text-[10px] text-muted tabular-nums">{r.atraso} atr.</span>
                    </div>
                  ))}
                </div>
              </div>
              {intel.games.map((g, i) => {
                const ja = saved.some((s) => s.loteria === atual && gameKey(s.numeros) === gameKey(g));
                return (
                  <div key={gameKey(g)} className="rounded-2xl border border-line bg-paper p-3">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold">Jogo {i + 1}</p>
                      <button
                        type="button"
                        className="text-sm font-semibold text-accent disabled:opacity-50"
                        onClick={() => salvar(g, "Inteligente")}
                        disabled={ja}
                      >
                        {ja ? "Salvo" : "Salvar"}
                      </button>
                    </div>
                    <Balls numbers={g} />
                    <p className="mt-2 text-xs text-muted tabular-nums">
                      Soma {g.reduce((sum, n) => sum + n, 0)} · {g.filter((n) => n % 2 === 0).length} pares
                    </p>
                  </div>
                );
              })}
            </div>
          ) : null}
        </section>
      )}

      <section className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Jogos salvos</h2>
          <p className="text-sm text-muted">{saved.length}</p>
        </div>
        <p className="sr-only" aria-live="polite">
          {notice}
        </p>
        {notice ? <p className="text-sm font-medium text-accent">{notice}</p> : null}
        {saved.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-line bg-card px-4 py-6 text-sm text-muted">
            Nenhum jogo salvo ainda. Monte um volante ou gere uma formulação e toque em salvar. Fica só neste aparelho.
          </p>
        ) : (
          saved.map((g) => {
            const meta = LOTERIAS[g.loteria];
            const compare = show && g.loteria === atual ? show : null;
            return (
              <article key={g.id} className="rounded-2xl border border-line bg-card p-4">
                <p className="text-sm font-semibold">
                  {meta.nome}
                  <span className="font-medium text-muted"> · {g.modo}</span>
                </p>
                <div className="mt-3" data-loteria={g.loteria}>
                  <Balls numbers={g.numeros} />
                </div>
                {compare ? <HitLine game={g.numeros} draw={compare} premioMin={meta.premioMin} /> : null}
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button type="button" className={`${ghostBtn} text-sm`} onClick={() => copiar(g.numeros)}>
                    <Copy className="size-4" aria-hidden="true" />
                    Copiar
                  </button>
                  <button
                    type="button"
                    className={`${ghostBtn} text-sm`}
                    onClick={() => setSaved((prev) => prev.filter((item) => item.id !== g.id))}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                    Apagar
                  </button>
                </div>
              </article>
            );
          })
        )}
      </section>

      <footer className="pb-4 text-sm text-muted">
        <p>Jogue com responsabilidade. Este app não vende apostas e não tem vínculo com a Caixa Econômica Federal.</p>
      </footer>
    </div>
  );
}

function HitLine({ game, draw, premioMin }: { game: number[]; draw: LatestDraw; premioMin: number }) {
  const h1 = countHits(game, draw.dezenas);
  const h2 = draw.dezenas2 ? countHits(game, draw.dezenas2) : 0;
  const prize = h1 >= premioMin || (draw.dezenas2 ? h2 >= premioMin : false);
  const text = draw.dezenas2
    ? `${hitsPhrase(h1, "no 1º")} · ${hitsPhrase(h2, "no 2º")}`
    : hitsPhrase(h1, `no concurso ${draw.numero}`);
  return <p className={`mt-3 text-sm ${prize ? "font-semibold text-accent" : "text-muted"}`}>{text}</p>;
}

function LatestCard({
  nome,
  draw,
  loading,
  refreshing,
  error,
  onRetry,
}: {
  nome: string;
  draw: LatestDraw | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (loading || !draw) {
    return (
      <section className="rounded-2xl border border-line bg-card p-4 shadow-ticket">
        <h2 className="font-display text-2xl font-bold tracking-wide">{nome}</h2>
        <p className="mt-3 text-sm text-muted">{error ? error : "Buscando o último concurso…"}</p>
        {error ? (
          <button type="button" className={`${primaryBtn} mt-4`} onClick={onRetry}>
            Tentar de novo
          </button>
        ) : null}
      </section>
    );
  }

  const digits = Number.isInteger(draw.premioEstimado) ? 0 : 2;

  return (
    <article className="overflow-hidden rounded-2xl border border-line bg-card shadow-ticket">
      <header className="flex items-center justify-between gap-3 bg-accent px-4 py-3 text-card">
        <h2 className="font-display text-2xl font-bold tracking-wide">{nome}</h2>
        {draw.acumulado == null ? null : (
          <span className="rounded-full bg-card px-2.5 py-1 text-xs font-semibold tracking-wide text-accent">
            {draw.acumulado ? "ACUMULOU" : "TEVE GANHADOR"}
          </span>
        )}
      </header>
      <div className="px-4 py-4">
        {draw.premioEstimado ? (
          <>
            <p className="text-xs font-semibold tracking-wide text-muted uppercase">Prêmio estimado</p>
            <p className="mt-1 font-display text-5xl font-bold leading-none text-accent tabular-nums">
              {formatBRL(draw.premioEstimado, digits)}
            </p>
            <p className="mt-2 text-sm text-muted">
              {draw.dataProximo ? `Próximo concurso em ${draw.dataProximo}` : "Próximo concurso"}
            </p>
          </>
        ) : null}
        <div className="mt-4 border-t border-dashed border-line pt-4">
          <p className="text-sm font-semibold">
            Concurso {draw.numero}
            {draw.dataApuracao ? <span className="font-medium text-muted"> · {draw.dataApuracao}</span> : null}
          </p>
          {draw.local ? <p className="mt-1 text-xs tracking-wide text-muted uppercase">{draw.local}</p> : null}
          {draw.dezenas2 ? <p className="mt-3 text-xs font-semibold tracking-wide text-muted uppercase">1º sorteio</p> : null}
          <div className="mt-3">
            <Balls numbers={draw.dezenas} />
          </div>
          {draw.dezenas2 ? (
            <>
              <p className="mt-4 text-xs font-semibold tracking-wide text-muted uppercase">2º sorteio</p>
              <div className="mt-3">
                <Balls numbers={draw.dezenas2} />
              </div>
            </>
          ) : null}
          {draw.faixas.length > 0 ? (
            <ul className="mt-4 flex flex-col gap-2">
              {draw.faixas.map((f) => (
                <li key={f.descricao} className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="text-muted">{f.descricao}</span>
                  <span className="text-right text-ink tabular-nums">
                    {f.ganhadores === 0
                      ? "Nenhum"
                      : `${f.ganhadores.toLocaleString("pt-BR")} · ${formatBRL(f.valor, 2)}`}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          <button
            type="button"
            className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-accent disabled:opacity-50"
            onClick={onRetry}
            disabled={refreshing}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            {refreshing ? "Atualizando…" : "Atualizar"}
          </button>
        </div>
      </div>
    </article>
  );
}
