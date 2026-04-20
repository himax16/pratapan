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

export async function lowercaseText(text: string): Promise<string> {
  const res = await fetch(`${API}/v1/lowercase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return data.result as string
}
