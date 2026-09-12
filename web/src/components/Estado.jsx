export function Carregando({ texto = 'Carregando…' }) {
  return <div style={{ padding: 24, color: 'var(--texto-secundario)' }}>{texto}</div>
}

export function Erro({ mensagem, dica }) {
  return (
    <div
      className="card"
      style={{ padding: 20, borderLeft: '4px solid var(--destaque)', color: 'var(--texto-principal)' }}
    >
      <strong style={{ color: 'var(--destaque)' }}>Não foi possível carregar os dados.</strong>
      <p style={{ margin: '8px 0 0', fontSize: 13.5 }}>{mensagem}</p>
      {dica && <p style={{ margin: '8px 0 0', fontSize: 12.5, color: 'var(--texto-secundario)' }}>{dica}</p>}
    </div>
  )
}
