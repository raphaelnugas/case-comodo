import { useState } from 'react'
import { formatarMoeda, formatarNumero } from '../lib/format'
import './indicador.css'

function formatarValor(indicador) {
  if (indicador.formato === 'moeda') return formatarMoeda(indicador.valor)
  if (indicador.formato === 'inteiro') return formatarNumero(indicador.valor)
  return indicador.valor ?? '—'
}

export default function Indicador({ indicador }) {
  const [emHover, setEmHover] = useState(false)
  const [fixado, setFixado] = useState(false)
  const aberto = emHover || fixado

  return (
    <div
      className="card indicador"
      onMouseEnter={() => setEmHover(true)}
      onMouseLeave={() => setEmHover(false)}
      onClick={() => setFixado((v) => !v)}
      tabIndex={0}
      role="button"
      aria-expanded={aberto}
    >
      <div className="indicador-label">{indicador.label}</div>
      <div className="indicador-valor">{formatarValor(indicador)}</div>
      {indicador.detalhe && <div className="indicador-detalhe">{indicador.detalhe}</div>}
      <div className="indicador-dica">clique para ver a origem do número</div>

      {aberto && (
        <div className="indicador-popover" onClick={(e) => e.stopPropagation()}>
          <strong>Fórmula</strong>
          <p>{indicador.formula}</p>
          {indicador.nota && (
            <>
              <strong>Observação</strong>
              <p>{indicador.nota}</p>
            </>
          )}
          <strong>Arquivos de origem</strong>
          <ul>
            {indicador.fonte?.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <strong>Consulta SQL</strong>
          <p className="indicador-sql-arquivo">{indicador.sql_arquivo}</p>
          <strong>Registros utilizados</strong>
          <p>{formatarNumero(indicador.registros_utilizados)}</p>
        </div>
      )}
    </div>
  )
}
