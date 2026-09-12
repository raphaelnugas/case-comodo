import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Parte1Github from './pages/Parte1Github'
import Parte2Analise from './pages/Parte2Analise'
import Parte3Prevendas from './pages/Parte3Prevendas'
import './styles/layout.css'

export default function App() {
  return (
    <div className="layout">
      <Sidebar />
      <main className="conteudo">
        <Routes>
          <Route path="/" element={<Parte1Github />} />
          <Route path="/analise-comercial" element={<Parte2Analise />} />
          <Route path="/prevendas" element={<Parte3Prevendas />} />
        </Routes>
      </main>
    </div>
  )
}
