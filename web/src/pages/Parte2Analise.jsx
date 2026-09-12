import { useMemo, useState } from 'react'
import { useJson } from '../lib/useDataFetch'
import { Carregando, Erro } from '../components/Estado'
import Indicador from '../components/Indicador'
import Funil from '../components/Funil'
import SqlDisclosure from '../components/SqlDisclosure'
import { formatarMoeda, formatarNumero } from '../lib/format'
import { baixarCsv } from '../lib/csv'
import '../components/indicador.css'

export default function Parte2Analise() {
  const { dados, carregando, erro } = useJson('data/analise_metadata.json')
  const [plataforma, setPlataforma] = useState('todas')
  const [campanha, setCampanha] = useState('todas')

  const custoLinhas = dados?.secoes.custo_por_campanha.linhas ?? []
  const funilLinhas = dados?.secoes.funil_por_campanha.linhas ?? []
  const ticketLinhas = dados?.secoes.ticket_medio_receita.linhas ?? []

  const plataformas = useMemo(
    () => Array.from(new Set(custoLinhas.map((r) => r.plataforma).filter(Boolean))),
    [custoLinhas]
  )
  const campanhas = useMemo(
    () => custoLinhas.map((r) => ({ id: r.campanha_id, nome: r.nome_campanha_amigavel })),
    [custoLinhas]
  )

  const passaFiltro = (linha) => {
    if (plataforma !== 'todas' && linha.plataforma !== plataforma) return false
    if (campanha !== 'todas' && linha.campanha_id !== campanha) return false
    return true
  }

  const custoFiltrado = custoLinhas.filter(passaFiltro)
  const funilFiltrado = funilLinhas.filter((l) => campanha === 'todas' || l.campanha_id === campanha)
  const ticketFiltrado = ticketLinhas.filter((l) => campanha === 'todas' || l.campanha_id === campanha)

  if (carregando) return <Carregando texto="Carregando análise comercial…" />
  if (erro)
    return (
      <Erro
        mensagem={String(erro)}
        dica="Rode `python -m src.parte2_analise.build_database && python -m src.parte2_analise.export_web`."
      />
    )

  return (
    <div>
      <header className="pagina-cabecalho">
        <h1 className="pagina-titulo">Parte 2 — Análise comercial</h1>
        <span className="pagina-fonte-nota">
          Fontes: dados/investimento_midia.csv, dados/leads.csv, dados/vendas.csv — processadas via SQLite/SQL.
        </span>
      </header>

      <div className="indicadores-grid">
        {dados.indicadores_principais.map((ind) => (
          <Indicador key={ind.label} indicador={ind} />
        ))}
      </div>

      <LimitacoesDados limitacoes={dados.limitacoes} />

      <div style={{ display: 'flex', gap: 12, margin: '28px 0 -6px', flexWrap: 'wrap' }}>
        <select value={plataforma} onChange={(e) => setPlataforma(e.target.value)}>
          <option value="todas">Todas as plataformas</option>
          {plataformas.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select value={campanha} onChange={(e) => setCampanha(e.target.value)}>
          <option value="todas">Todas as campanhas</option>
          {campanhas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </select>
      </div>

      <section className="secao">
        <h2 className="secao-titulo">{dados.secoes.custo_por_campanha.titulo}</h2>
        <p className="secao-descricao">{dados.secoes.custo_por_campanha.descricao}</p>
        <SqlDisclosure secao={dados.secoes.custo_por_campanha} />
        <div style={{ marginBottom: 10 }}>
          <button className="btn btn-outline" onClick={() => baixarCsv('custo_por_campanha_filtrado.csv', custoFiltrado)}>
            Baixar CSV filtrado
          </button>
        </div>
        <div className="card scroll-x">
          <table>
            <thead>
              <tr>
                <th>Campanha</th>
                <th>Plataforma</th>
                <th>Leads</th>
                <th>Vendas</th>
                <th>Investimento</th>
                <th>Custo/lead</th>
                <th>Custo/venda</th>
              </tr>
            </thead>
            <tbody>
              {custoFiltrado.map((r) => (
                <tr key={r.campanha_id}>
                  <td>
                    <div>{r.nome_campanha_amigavel}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--texto-secundario)' }}>
                      {r.campanha_id}
                      {r.nome_campanha_real ? ` · nome real: ${r.nome_campanha_real}` : ''}
                    </div>
                  </td>
                  <td>{r.plataforma ?? '—'}</td>
                  <td>{formatarNumero(r.total_leads)}</td>
                  <td>{formatarNumero(r.total_vendas)}</td>
                  <td>{r.gasto_total !== null ? formatarMoeda(r.gasto_total) : 'sem dado'}</td>
                  <td>{r.custo_por_lead !== null ? formatarMoeda(r.custo_por_lead) : '—'}</td>
                  <td>{r.custo_por_venda !== null ? formatarMoeda(r.custo_por_venda) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="secao">
        <h2 className="secao-titulo">{dados.secoes.funil_por_campanha.titulo}</h2>
        <p className="secao-descricao">{dados.secoes.funil_por_campanha.descricao}</p>
        <SqlDisclosure secao={dados.secoes.funil_por_campanha} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {funilFiltrado.map((linha) => (
            <Funil key={linha.campanha_id} linha={linha} />
          ))}
        </div>
      </section>

      <section className="secao">
        <h2 className="secao-titulo">{dados.secoes.ticket_medio_receita.titulo}</h2>
        <p className="secao-descricao">{dados.secoes.ticket_medio_receita.descricao}</p>
        <SqlDisclosure secao={dados.secoes.ticket_medio_receita} />
        <div style={{ marginBottom: 10 }}>
          <button className="btn btn-outline" onClick={() => baixarCsv('ticket_medio_receita_filtrado.csv', ticketFiltrado)}>
            Baixar CSV filtrado
          </button>
        </div>
        <div className="card scroll-x">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Campanha</th>
                <th>Vendas</th>
                <th>Ticket médio</th>
                <th>Receita total</th>
              </tr>
            </thead>
            <tbody>
              {ticketFiltrado.map((r) => (
                <tr key={r.campanha_id}>
                  <td>{r.rank_ticket_medio}</td>
                  <td>{r.nome_campanha_amigavel}</td>
                  <td>{formatarNumero(r.total_vendas)}</td>
                  <td>{formatarMoeda(r.ticket_medio)}</td>
                  <td>{formatarMoeda(r.receita_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function LimitacoesDados({ limitacoes }) {
  const [aberto, setAberto] = useState(false)
  if (!limitacoes?.length) return null
  return (
    <div className="card" style={{ padding: '14px 18px', marginTop: 18, borderLeft: '4px solid var(--destaque-secundario)' }}>
      <button
        onClick={() => setAberto((v) => !v)}
        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontWeight: 600, fontSize: 13 }}
      >
        {aberto ? '▾' : '▸'} Limitações dos dados e inferências assumidas ({limitacoes.length})
      </button>
      {aberto && (
        <ul style={{ marginTop: 10, fontSize: 12.5, color: 'var(--texto-secundario)', lineHeight: 1.6 }}>
          {limitacoes.map((l, i) => (
            <li key={i} style={{ marginBottom: 6 }}>
              {l}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
