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
  // ... perfil de soma, pares, baixos e sequências, depois o sorteio ponderado
  return { scores, ranking, profile };
}
