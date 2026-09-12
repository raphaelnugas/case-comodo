// Parser/gerador de CSV simples — suficiente para os arquivos deste projeto
// (sem aspas escapadas complexas, uma vírgula como separador).

export function parseCsv(texto) {
  const linhas = texto.replace(/\r\n/g, '\n').trim().split('\n')
  if (linhas.length === 0 || linhas[0] === '') return []
  const cabecalho = splitLinha(linhas[0])
  return linhas.slice(1).map((linha) => {
    const valores = splitLinha(linha)
    const obj = {}
    cabecalho.forEach((chave, i) => {
      obj[chave] = valores[i] ?? ''
    })
    return obj
  })
}

function splitLinha(linha) {
  // suporta campos entre aspas contendo vírgula
  const resultado = []
  let atual = ''
  let dentroDeAspas = false
  for (let i = 0; i < linha.length; i++) {
    const c = linha[i]
    if (c === '"') {
      dentroDeAspas = !dentroDeAspas
    } else if (c === ',' && !dentroDeAspas) {
      resultado.push(atual)
      atual = ''
    } else {
      atual += c
    }
  }
  resultado.push(atual)
  return resultado
}

export function toCsv(linhas) {
  if (!linhas || linhas.length === 0) return ''
  const colunas = Object.keys(linhas[0])
  const escapa = (valor) => {
    const texto = valor === null || valor === undefined ? '' : String(valor)
    return /[",\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto
  }
  const cabecalho = colunas.join(',')
  const corpo = linhas.map((linha) => colunas.map((c) => escapa(linha[c])).join(','))
  return [cabecalho, ...corpo].join('\n')
}

export function baixarCsv(nomeArquivo, linhas) {
  const conteudo = toCsv(linhas)
  const blob = new Blob([conteudo], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nomeArquivo
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
