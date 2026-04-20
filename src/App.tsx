import { useEffect, useState } from 'react'
import { waitForSidecar, lowercaseText } from './lib/sidecar'
import './App.css'

function App() {
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const [ready, setReady] = useState(false)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    waitForSidecar().then(setReady)
  }, [])

  async function handleConvert() {
    if (!input || pending || !ready) return
    setPending(true)
    try {
      setOutput(await lowercaseText(input))
    } catch (e) {
      setOutput(`error: ${e}`)
    } finally {
      setPending(false)
    }
  }

  return (
    <div id="lowercaser">
      <h1>Lowercase Converter</h1>
      {!ready && <p className="status">Starting Python server…</p>}
      <div className="row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleConvert()}
          placeholder="Type something..."
          disabled={!ready || pending}
        />
        <button onClick={handleConvert} disabled={!ready || pending || !input}>
          {pending ? '…' : 'Convert'}
        </button>
      </div>
      {output && <pre className="output">{output}</pre>}
    </div>
  )
}

export default App
