import { useMemo, useState } from 'react'
import { useCsv, useJson } from '../lib/useDataFetch'
import { Carregando, Erro } from '../components/Estado'
import { formatarData, formatarDataCurta, formatarNumero } from '../lib/format'
import { baixarCsv } from '../lib/csv'

const ROTULOS_STATUS = {
  sucesso: 'Atualizado',
  erro: 'Erro',
  sucesso_com_divergencia: 'Sucesso (com divergência)',
  em_andamento: 'Em andamento',
}

// Um "erro" na última tentativa não significa que os dados exibidos estão errados —
// a escrita é atômica, então a tabela abaixo continua sendo a da última coleta bem-
// sucedida. Só tratamos isso como erro "de verdade" (vermelho) quando quem falhou foi
// a execução agendada das 6h — o que de fato é um problema de produção a resolver.
// Qualquer outra falha (um teste manual, um rate-limit local sem token) é só um sinal
// de que o snapshot pode estar desatualizado, não de que algo está incorreto.
function calcularExibicaoStatus(status) {
  if (status.status === 'erro') {
    if (status.origem_execucao === 'agendado') {
      return { classe: 'erro', rotulo: 'Erro na coleta agendada' }
    }
    return { classe: 'desatualizado', rotulo: 'Desatualizado' }
  }
  return { classe: status.status, rotulo: ROTULOS_STATUS[status.status] ?? status.status }
}

export default function Parte1Github() {
  const status = useJson('data/github_collection_status.json')
  const csv = useCsv('data/github_repos_apache.csv')
  const [busca, setBusca] = useState('')

  const linhasFiltradas = useMemo(() => {
    if (!csv.linhas) return []
    const termo = busca.trim().toLowerCase()
    if (!termo) return csv.linhas
    return csv.linhas.filter(
      (r) => r.nome.toLowerCase().includes(termo) || r.linguagem_principal.toLowerCase().includes(termo)
    )
  }, [csv.linhas, busca])

  return (
    <div>
      <header className="pagina-cabecalho">
        <h1 className="pagina-titulo">Parte 1 — Coleta GitHub</h1>
        <span className="pagina-fonte-nota">
          Dados coletados pela API pública do GitHub
          (<code>api.github.com/orgs/&#123;org&#125;/repos</code>), sem amostragem, e
          disponibilizados aqui pelo último snapshot processado — esta página lê um
          arquivo estático, não chama a API a cada visita.
        </span>
      </header>

      {status.carregando && <Carregando texto="Carregando log da última execução…" />}
      {status.erro && (
        <Erro
          mensagem={String(status.erro)}
          dica="Rode `python -m src.parte1_github.collect_repos` para gerar o status e o CSV."
        />
      )}
      {status.dados && <LogExecucao status={status.dados} />}

      <section className="secao">
        <h2 className="secao-titulo">Repositórios coletados</h2>
        <p className="secao-descricao">
          Organização <strong>{status.dados?.organizacao ?? '—'}</strong> — busque por nome ou linguagem.
        </p>

        <div style={{ display: 'flex', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
          <input
            type="search"
            placeholder="Buscar por nome ou linguagem..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            style={{ minWidth: 260 }}
          />
          <button
            className="btn btn-primary"
            onClick={() => csv.linhas && baixarCsv(`github_repos_${status.dados?.organizacao ?? 'org'}.csv`, csv.linhas)}
            disabled={!csv.linhas}
          >
            Baixar CSV
          </button>
          <span style={{ alignSelf: 'center', fontSize: 12.5, color: 'var(--texto-secundario)' }}>
            {formatarNumero(linhasFiltradas.length)} de {formatarNumero(csv.linhas?.length ?? 0)} repositórios
          </span>
        </div>

        {csv.carregando && <Carregando texto="Carregando repositórios…" />}
        {csv.erro && (
          <Erro
            mensagem={String(csv.erro)}
            dica="O CSV é gerado por `collect_repos.py` em data/output/ e espelhado em web/public/data/."
          />
        )}
        {csv.linhas && (
          <div className="card scroll-x" style={{ maxHeight: 560, overflowY: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Descrição</th>
                  <th>Linguagem</th>
                  <th>Estrelas</th>
                  <th>Forks</th>
                  <th>Criado em</th>
                  <th>Atualizado em</th>
                </tr>
              </thead>
              <tbody>
                {linhasFiltradas.slice(0, 500).map((r) => (
                  <tr key={r.nome}>
                    <td>
                      <a href={`https://github.com/${status.dados?.organizacao}/${r.nome}`} target="_blank" rel="noreferrer">
                        {r.nome}
                      </a>
                    </td>
                    <td style={{ whiteSpace: 'normal', maxWidth: 360 }}>{r.descricao || '—'}</td>
                    <td>{r.linguagem_principal}</td>
                    <td>{formatarNumero(Number(r.estrelas))}</td>
                    <td>{formatarNumero(Number(r.forks))}</td>
                    <td>{formatarDataCurta(r.criado_em)}</td>
                    <td>{formatarDataCurta(r.atualizado_em)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {linhasFiltradas.length > 500 && (
              <p style={{ padding: 12, fontSize: 12, color: 'var(--texto-secundario)' }}>
                Mostrando os primeiros 500 resultados — refine a busca para ver outros.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

function LogExecucao({ status }) {
  const exibicao = calcularExibicaoStatus(status)
  const eDesatualizado = exibicao.classe === 'desatualizado'

  return (
    <div className="card" style={{ padding: 18, marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <div>
          <strong style={{ fontSize: 14 }}>Última execução</strong>
          <div style={{ fontSize: 12.5, color: 'var(--texto-secundario)', marginTop: 2 }}>
            {formatarData(status.inicio)} → {formatarData(status.fim)}
          </div>
        </div>
        <span className={`badge badge-${exibicao.classe}`}>{exibicao.rotulo}</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 14,
          marginTop: 16,
        }}
      >
        <Metrica label="Registros processados" valor={formatarNumero(status.registros_processados)} />
        <Metrica label="Registros esperados" valor={formatarNumero(status.registros_esperados)} />
        <Metrica label="Páginas percorridas" valor={formatarNumero(status.paginas_percorridas)} />
        <Metrica label="Duração" valor={`${status.duracao_segundos}s`} />
      </div>

      {status.erro && eDesatualizado && (
        <p style={{ marginTop: 14, fontSize: 12.5, color: '#8a6d1a' }}>
          <strong>A tabela abaixo é da última coleta bem-sucedida.</strong> A tentativa
          de atualização mais recente não deu certo (detalhe técnico: {status.erro}),
          mas nenhum dado exibido está incorreto por causa disso.
        </p>
      )}
      {status.erro && !eDesatualizado && (
        <p style={{ marginTop: 14, fontSize: 12.5, color: 'var(--destaque)' }}>
          <strong>A coleta agendada das 6h falhou:</strong> {status.erro}
        </p>
      )}
      {status.sha256_csv && (
        <p style={{ marginTop: 10, fontSize: 11.5, color: '#a8a8a8', fontFamily: 'monospace' }}>
          sha256 do CSV: {status.sha256_csv}
        </p>
      )}
    </div>
  )
}

function Metrica({ label, valor }) {
  return (
    <div>
      <div style={{ fontSize: 11.5, color: 'var(--texto-secundario)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{valor}</div>
    </div>
  )
}
