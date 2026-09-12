import { NavLink } from 'react-router-dom'

const ITENS = [
  { to: '/', label: 'Parte 1 — Coleta GitHub', sub: 'Ingestão via API' },
  { to: '/analise-comercial', label: 'Parte 2 — Análise comercial', sub: 'Funil, custo e receita' },
  { to: '/prevendas', label: 'Parte 3 — Pré-vendas', sub: 'Classificação com IA' },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-marca">Cômodo Planejados</div>
      <div className="sidebar-subtitulo">Case técnico — Python, Dados &amp; IA</div>
      <nav className="sidebar-nav">
        {ITENS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `sidebar-link${isActive ? ' ativo' : ''}`}
          >
            <span>{item.label}</span>
            <small>{item.sub}</small>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-rodape">
        Dados sintéticos (maio–junho de 2026) exceto a Parte 1, que consulta a API
        pública do GitHub em tempo real.
      </div>
    </aside>
  )
}
