const ETAPAS = [
  { chave: 'alcancou_novo', label: 'Novo' },
  { chave: 'alcancou_em_atendimento', label: 'Em atendimento' },
  { chave: 'alcancou_qualificado', label: 'Qualificado' },
  { chave: 'alcancou_briefing', label: 'Briefing' },
  { chave: 'alcancou_proposta', label: 'Proposta' },
  { chave: 'alcancou_vendido', label: 'Vendido' },
]

const PERDAS = [
  'pct_perda_novo_para_atendimento',
  'pct_perda_atendimento_para_qualificado',
  'pct_perda_qualificado_para_briefing',
  'pct_perda_briefing_para_proposta',
  'pct_perda_proposta_para_vendido',
]

export default function Funil({ linha }) {
  const max = linha.alcancou_novo || 1

  return (
    <div className="card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <strong>{linha.nome_campanha_amigavel}</strong>
        <span style={{ fontSize: 11.5, color: 'var(--texto-secundario)' }}>
          {linha.total_leads} leads · {linha.total_perdidos} perdidos ({linha.pct_perdidos_do_total}%)
        </span>
      </div>

      <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end' }}>
        {ETAPAS.map((etapa, i) => {
          const valor = linha[etapa.chave]
          const largura = Math.max(6, (valor / max) * 100)
          const perda = i > 0 ? linha[PERDAS[i - 1]] : null
          return (
            <div key={etapa.chave} style={{ flex: 1, minWidth: 0 }}>
              <div
                title={`${etapa.label}: ${valor} leads`}
                style={{
                  height: 34,
                  width: `${largura}%`,
                  minWidth: 22,
                  background: i === ETAPAS.length - 1 ? 'var(--verde)' : 'var(--destaque)',
                  opacity: 0.35 + 0.65 * (valor / max),
                  borderRadius: 6,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                {valor}
              </div>
              <div style={{ fontSize: 10, color: 'var(--texto-secundario)', marginTop: 4, textAlign: 'center' }}>
                {etapa.label}
              </div>
              {perda !== null && (
                <div style={{ fontSize: 9.5, color: 'var(--destaque-secundario)', textAlign: 'center' }}>
                  −{perda}%
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
