# Front-end (Cômodo Planejados — case técnico)

Interface React (Vite) para as 3 partes do case. Não é avaliada pelo case em si — ver
justificativa no [README raiz](../README.md).

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # build de produção em dist/
```

Consome os arquivos gerados pelos scripts Python em `public/data/` (JSON/CSV).
Rodar os scripts em `../src/` regenera esses arquivos — nenhum componente aqui
precisa mudar. Ver [`../docs/FLUXO_DE_DADOS.md`](../docs/FLUXO_DE_DADOS.md).
