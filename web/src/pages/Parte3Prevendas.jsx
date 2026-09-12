import { useMemo, useRef, useState } from 'react'
import { useJson } from '../lib/useDataFetch'
import { Carregando, Erro } from '../components/Estado'
import { formatarData } from '../lib/format'
import './parte3.css'

const CLASSES = [
  { chave: 'quente', label: 'Quente' },
  { chave: 'morno', label: 'Morno' },
  { chave: 'frio', label: 'Frio' },
  { chave: 'fora_do_perfil', label: 'Fora do perfil' },
  { chave: 'falha_tecnica', label: 'Falha técnica' },
]

export default function Parte3Prevendas() {
  const classificacoes = useJson('data/classificacoes_prevendas.json')
  const conversas = useJson('data/conversas_prevendas.json')
  const [filtro, setFiltro] = useState('todas')
  const [selecionadoId, setSelecionadoId] = useState(null)
  const [mensagemDestacada, setMensagemDestacada] = useState(null)
  const refsMensagens = useRef({})

  const conversasPorId = useMemo(() => {
    const mapa = {}
    ;(conversas.dados ?? []).forEach((c) => (mapa[c.conversa_id] = c))
    return mapa
  }, [conversas.dados])

  const lista = classificacoes.dados ?? []

  const contagens = useMemo(() => {
    const c = { quente: 0, morno: 0, frio: 0, fora_do_perfil: 0, falha_tecnica: 0 }
    lista.forEach((item) => {
      const chave = item.status === 'falha_tecnica' ? 'falha_tecnica' : item.classificacao
      if (chave in c) c[chave] += 1
    })
    return c
  }, [lista])

  const listaFiltrada = useMemo(() => {
    if (filtro === 'todas') return lista
    return lista.filter((item) => (item.status === 'falha_tecnica' ? 'falha_tecnica' : item.classificacao) === filtro)
  }, [lista, filtro])

  const selecionado = listaFiltrada.find((c) => c.conversa_id === selecionadoId) ?? listaFiltrada[0] ?? null

  const irParaMensagem = (numero) => {
    setMensagemDestacada(numero)
    refsMensagens.current[numero]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const selecionarConversa = (id) => {
    setSelecionadoId(id)
    setMensagemDestacada(null)
  }

  if (classificacoes.carregando || conversas.carregando) return <Carregando texto="Carregando conversas…" />

  if (classificacoes.erro) {
    return (
      <div>
        <CabecalhoPagina />
        <Erro
          mensagem="Ainda não há classificações geradas (data/classificacoes_prevendas.json não encontrado)."
          dica="Rode `python -m src.parte3_prevendas.classify` com GEMINI_API_KEY definido em .env para gerar os resultados reais."
        />
      </div>
    )
  }

  return (
    <div>
      <CabecalhoPagina />

      <div className="indicadores-grid" style={{ marginBottom: 22 }}>
        {CLASSES.map((c) => (
          <button
            key={c.chave}
            onClick={() => setFiltro(filtro === c.chave ? 'todas' : c.chave)}
            className="card"
            style={{
              padding: '16px 18px',
              textAlign: 'left',
              cursor: 'pointer',
              border: filtro === c.chave ? '2px solid var(--destaque)' : undefined,
            }}
          >
            <div style={{ fontSize: 12, color: 'var(--texto-secundario)' }}>{c.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{contagens[c.chave] ?? 0}</div>
          </button>
        ))}
      </div>

      <div className="p3-layout">
        <div className="card p3-lista">
          {listaFiltrada.map((item) => (
            <button
              key={item.conversa_id}
              className={`p3-item${selecionado?.conversa_id === item.conversa_id ? ' ativo' : ''}`}
              onClick={() => selecionarConversa(item.conversa_id)}
            >
              <div className="p3-item-topo">
                <span className="p3-item-id">{item.conversa_id}</span>
                <span className={`badge badge-${item.status === 'falha_tecnica' ? 'falha_tecnica' : item.classificacao}`}>
                  {item.status === 'falha_tecnica' ? 'falha técnica' : item.classificacao}
                </span>
              </div>
              <div className="p3-item-resumo">
                {item.status === 'falha_tecnica' ? item.erro : item.resumo_para_o_vendedor}
              </div>
            </button>
          ))}
          {listaFiltrada.length === 0 && (
            <p style={{ fontSize: 12.5, color: 'var(--texto-secundario)', padding: 8 }}>
              Nenhuma conversa nessa classificação.
            </p>
          )}
        </div>

        {selecionado && (
          <DetalheConversa
            item={selecionado}
            conversa={conversasPorId[selecionado.conversa_id]}
            refsMensagens={refsMensagens}
            mensagemDestacada={mensagemDestacada}
          />
        )}

        {selecionado && <PainelLateral item={selecionado} onEvidenciaClick={irParaMensagem} />}
      </div>
    </div>
  )
}

function CabecalhoPagina() {
  return (
    <header className="pagina-cabecalho">
      <h1 className="pagina-titulo">Parte 3 — Pré-vendas</h1>
      <span className="pagina-fonte-nota">
        Classificação gerada por LLM a partir de dados/conversas_prevendas.json. As conversas são
        sintéticas e não têm vínculo individual garantido com leads.csv/vendas.csv.
      </span>
    </header>
  )
}

function DetalheConversa({ item, conversa, refsMensagens, mensagemDestacada }) {
  if (item.status === 'falha_tecnica') {
    return (
      <div className="card" style={{ padding: 20 }}>
        <Erro
          mensagem={`Falha técnica ao classificar ${item.conversa_id}: ${item.erro}`}
          dica="Esta conversa NÃO foi classificada como 'frio' — está sinalizada para revisão humana."
        />
      </div>
    )
  }

  return (
    <div className="card" style={{ padding: 20, maxHeight: '74vh', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <strong style={{ fontSize: 15 }}>{item.conversa_id}</strong>
        <span className={`badge badge-${item.classificacao}`}>{item.classificacao}</span>
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--texto-secundario)', marginBottom: 16 }}>
        prioridade {item.prioridade} · classificado por {item.modelo_usado ?? '—'} em {formatarData(item.classificado_em)}
      </div>

      <p style={{ fontSize: 13.5, lineHeight: 1.6 }}>{item.resumo_para_o_vendedor}</p>

      <SubTitulo>Próxima ação recomendada</SubTitulo>
      <p style={{ fontSize: 13 }}>{item.proxima_acao}</p>

      <SubTitulo>Sinais observados</SubTitulo>
      <div>
        {item.sinais?.map((s, i) => (
          <span key={i} className="p3-chip">
            {s}
          </span>
        ))}
      </div>

      {item.alertas?.length > 0 && (
        <>
          <SubTitulo>Alertas</SubTitulo>
          <div>
            {item.alertas.map((a, i) => (
              <span key={i} className="p3-chip p3-chip-alerta">
                ⚠ {a}
              </span>
            ))}
          </div>
        </>
      )}

      {item.revisao_humana_recomendada && (
        <p style={{ fontSize: 12, color: 'var(--destaque-secundario)', marginTop: 12 }}>
          <strong>Revisão humana recomendada.</strong> {item.motivo_revisao_humana}
        </p>
      )}

      <SubTitulo>Diálogo original</SubTitulo>
      <div style={{ fontSize: 11, color: 'var(--texto-secundario)', marginBottom: 8 }}>
        Origem: dados/conversas_prevendas.json — campanha de origem: {conversa?.campanha_id ?? '—'}
      </div>
      <div>
        {conversa?.mensagens.map((m, i) => {
          const numero = i + 1
          return (
            <div
              key={numero}
              ref={(el) => (refsMensagens.current[numero] = el)}
              className={`p3-mensagem ${m.de}${mensagemDestacada === numero ? ' destacada' : ''}`}
            >
              <small>
                [{numero}] {m.de}
              </small>
              {m.texto}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PainelLateral({ item, onEvidenciaClick }) {
  if (item.status === 'falha_tecnica') return null

  return (
    <div className="card" style={{ padding: 18 }}>
      <SubTitulo>Evidências</SubTitulo>
      <p style={{ fontSize: 11, color: 'var(--texto-secundario)', marginTop: -4, marginBottom: 10 }}>
        Clique para destacar a mensagem correspondente no diálogo.
      </p>
      {item.evidencias?.map((ev, i) => (
        <button key={i} className="p3-evidencia" onClick={() => onEvidenciaClick(ev.numero_mensagem)}>
          <strong>[{ev.numero_mensagem}]</strong> {ev.trecho}
        </button>
      ))}
      {item.avisos_validacao?.length > 0 && (
        <>
          <SubTitulo>Avisos de validação</SubTitulo>
          <ul style={{ fontSize: 11, color: 'var(--texto-secundario)', paddingLeft: 16 }}>
            {item.avisos_validacao.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function SubTitulo({ children }) {
  return (
    <div
      style={{
        fontSize: 11,
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        color: 'var(--texto-secundario)',
        marginTop: 18,
        marginBottom: 6,
      }}
    >
      {children}
    </div>
  )
}
