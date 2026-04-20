import { useEffect, useState } from 'react'
import {
  type SparkRow,
  sparkAdd,
  sparkRemove,
  sparkView,
  waitForSidecar,
} from './lib/sidecar'
import './App.css'

function App() {
  const [input, setInput] = useState('')
  const [rows, setRows] = useState<SparkRow[]>([])
  const [ready, setReady] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [tableVisible, setTableVisible] = useState(false)

  useEffect(() => {
    waitForSidecar().then(setReady)
  }, [])

  async function handleAdd() {
    if (!input.trim() || pending || !ready) return
    setPending(true)
    setError('')
    try {
      await sparkAdd(input.trim())
      setInput('')
      if (tableVisible) await refreshView()
    } catch (e) {
      setError(`Add failed: ${e}`)
    } finally {
      setPending(false)
    }
  }

  async function refreshView() {
    const data = await sparkView()
    setRows(data)
    setTableVisible(true)
  }

  async function handleView() {
    if (pending || !ready) return
    setPending(true)
    setError('')
    try {
      await refreshView()
    } catch (e) {
      setError(`View failed: ${e}`)
    } finally {
      setPending(false)
    }
  }

  async function handleRemove(id: string) {
    if (pending || !ready) return
    setPending(true)
    setError('')
    try {
      await sparkRemove(id)
      await refreshView()
    } catch (e) {
      setError(`Remove failed: ${e}`)
    } finally {
      setPending(false)
    }
  }

  return (
    <div id="spark-app">
      <h1>Spark Database</h1>
      {!ready && <p className="status">Starting Python server…</p>}

      <div className="row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="Enter a value…"
          disabled={!ready || pending}
        />
        <button onClick={handleAdd} disabled={!ready || pending || !input.trim()}>
          Add to Spark
        </button>
        <button
          className="secondary"
          onClick={handleView}
          disabled={!ready || pending}
        >
          View Database
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {tableVisible && (
        <div className="table-wrap">
          {rows.length === 0 ? (
            <p className="status">No entries in the database.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Value</th>
                  <th>ID</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.value}</td>
                    <td className="id-cell">{row.id}</td>
                    <td>
                      <button
                        className="remove"
                        onClick={() => handleRemove(row.id)}
                        disabled={pending}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default App
