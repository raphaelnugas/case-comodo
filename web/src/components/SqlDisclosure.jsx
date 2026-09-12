import { useState } from 'react'

export default function SqlDisclosure({ secao }) {
  const [aberto, setAberto] = useState(false)
  if (!secao) return null

  return (
    <div style={{ marginBottom: 14 }}>
      <button className="btn btn-outline" onClick={() => setAberto((v) => !v)}>
        {aberto ? 'Ocultar' : 'Ver'} consulta SQL ({secao.sql_arquivo})
      </button>
      {aberto && (
        <pre
          className="scroll-x"
          style={{
            marginTop: 10,
            background: '#151515',
            color: '#e8e8e8',
            padding: 16,
            borderRadius: 12,
            fontSize: 12,
            lineHeight: 1.6,
          }}
        >
          {secao.sql}
        </pre>
      )}
    </div>
  )
}
