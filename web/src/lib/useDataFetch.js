import { useEffect, useState } from 'react'
import { parseCsv } from './csv'

const BASE = import.meta.env.BASE_URL

export function useJson(caminho) {
  const [estado, setEstado] = useState({ dados: null, carregando: true, erro: null })

  useEffect(() => {
    let cancelado = false
    setEstado({ dados: null, carregando: true, erro: null })
    fetch(`${BASE}${caminho}`.replace('//', '/'))
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((dados) => {
        if (!cancelado) setEstado({ dados, carregando: false, erro: null })
      })
      .catch((erro) => {
        if (!cancelado) setEstado({ dados: null, carregando: false, erro })
      })
    return () => {
      cancelado = true
    }
  }, [caminho])

  return estado
}

export function useCsv(caminho) {
  const [estado, setEstado] = useState({ linhas: null, carregando: true, erro: null })

  useEffect(() => {
    let cancelado = false
    setEstado({ linhas: null, carregando: true, erro: null })
    fetch(`${BASE}${caminho}`.replace('//', '/'))
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.text()
      })
      .then((texto) => {
        if (!cancelado) setEstado({ linhas: parseCsv(texto), carregando: false, erro: null })
      })
      .catch((erro) => {
        if (!cancelado) setEstado({ linhas: null, carregando: false, erro })
      })
    return () => {
      cancelado = true
    }
  }, [caminho])

  return estado
}
