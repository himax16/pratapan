const API = 'http://127.0.0.1:48240'

export async function waitForSidecar(
  maxAttempts = 20,
  delayMs = 500,
): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const res = await fetch(`${API}/v1/connect`)
      if (res.ok) return true
    } catch {}
    await new Promise((r) => setTimeout(r, delayMs))
  }
  return false
}

export interface SparkRow {
  id: string
  value: string
}

export async function sparkAdd(text: string): Promise<SparkRow> {
  const res = await fetch(`${API}/v1/spark/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function sparkView(): Promise<SparkRow[]> {
  const res = await fetch(`${API}/v1/spark/view`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return data.rows as SparkRow[]
}

export async function sparkRemove(id: string): Promise<void> {
  const res = await fetch(`${API}/v1/spark/remove/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}
