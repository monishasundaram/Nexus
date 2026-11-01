export interface Link { source: string; target: string }

/** All nodes reachable from `start`. 'down' follows supplier -> dependent, 'up' goes backwards. Cycle-safe. */
export function reach(start: string, links: Link[], dir: 'up' | 'down'): Set<string> {
  const next = new Map<string, string[]>()
  for (const l of links) {
    const [from, to] = dir === 'down' ? [l.source, l.target] : [l.target, l.source]
    if (!next.has(from)) next.set(from, [])
    next.get(from)!.push(to)
  }
  const seen = new Set<string>()
  const queue = [start]
  while (queue.length) {
    const cur = queue.shift()!
    for (const nb of next.get(cur) ?? []) {
      if (nb !== start && !seen.has(nb)) {
        seen.add(nb)
        queue.push(nb)
      }
    }
  }
  return seen
}