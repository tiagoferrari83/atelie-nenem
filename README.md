# Ateliê - Sistema de Gestão

Sistema simples para gerenciar um ateliê de costura: cadastro de prestador de serviço,
clientes, serviços e matéria-prima, além de geração de orçamentos e ordens de serviço em PDF.

## Como rodar localmente

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

2. Copie o arquivo `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml`
   e preencha com os dados reais do Supabase:
   ```
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   - `url`: connection string do banco (Settings → Database → Connection pooler)
   - `storage_url`: URL do projeto (Settings → API → Project URL)
   - `storage_key`: a chave `anon` `public` (Settings → API → Project API keys)

3. **Crie o bucket de fotos no Supabase Storage** (passo manual, uma vez só):
   - No painel do Supabase, vá em **Storage** → **New bucket**
   - Nome: `orcamento-fotos`
   - Marque como **Public bucket** (para as fotos abrirem direto pela URL)
   - Salvar

4. Rode o app:
   ```
   streamlit run app.py
   ```

## Deploy no Streamlit Community Cloud

1. Suba este projeto para um repositório no GitHub — **sem o arquivo `secrets.toml`**
   (ele já está no `.gitignore`, só o `.example` deve ir para o Git).
2. Acesse [share.streamlit.io](https://share.streamlit.io), conecte seu GitHub e
   selecione o repositório.
3. Em **Settings → Secrets** do próprio Streamlit Cloud, cole o conteúdo do seu
   `secrets.toml` real (url, storage_url, storage_key).
4. Não esqueça do passo 3 acima (criar o bucket `orcamento-fotos` no Storage) —
   é feito uma vez só, direto no painel do Supabase, e vale tanto local quanto em produção.
5. Deploy!

## Estrutura

- `app.py` — roteador da navegação (menu lateral customizado) e inicialização do banco
- `pages/0_Dashboard.py` — dashboard: OS reabertas, OS em aberto e agenda de próximas entregas
- `database.py` — conexão com Supabase e criação/atualização das tabelas
- `constants.py` — labels e opções de tipo de pedido, status, etc.
- `storage.py` — upload/exclusão de fotos no Supabase Storage
- `pages/1_Prestador.py` — cadastro dos dados da empresa/ateliê (com logo)
- `pages/2_Clientes.py` — cadastro de clientes
- `pages/3_Servicos.py` — cadastro de serviços (por unidade, tempo ou metro)
- `pages/4_Materia_Prima.py` — cadastro de matéria-prima (por unidade, metro ou peso)
- `pages/50_Novo.py` — tela de escolha: Orçamento ou Ordem de Serviço
- `pages/51_Orcamento.py` — formulário de Orçamento (usa `formulario_orcamento.py`) — não aparece
  no menu lateral, só é acessível pelos botões em "Novo" ou "Editar"/"Criar OS" em Consultar
- `pages/52_Ordem_Servico.py` — formulário de Ordem de Serviço (idem acima) — também oculto do menu
- `formulario_orcamento.py` — lógica compartilhada dos dois formulários acima
- `pages/6_Consultar.py` — consulta documentos, edita, exclui, atualiza status, gera OS a partir de orçamento
- `pdf_generator.py` — geração dos PDFs de orçamento/ordem de serviço

## Fluxo de uso

1. Cadastre o **Prestador de Serviço** (seus dados, aparecem no cabeçalho do PDF)
2. Cadastre **Clientes** (pode usar a busca por nome/telefone/email para encontrar rápido)
3. Cadastre **Serviços** e/ou **Matéria-Prima** (busca por nome disponível em Serviços)
   (ou cadastre na hora, veja abaixo)
4. No menu **Novo**, escolha se vai criar um Orçamento ou uma Ordem de Serviço
   (são duas telas separadas, para não confundir os dois fluxos). Em qualquer
   uma: escolha o tipo de pedido (Confecção, Personalização ou Criação), o
   cliente, adicione um ou mais **serviços** e, opcionalmente, **matéria-prima
   usada em cada serviço** (a matéria-prima é sempre um subitem de um serviço
   específico, não um item avulso). O subtotal de cada serviço soma seu valor +
   os materiais dele; o total geral soma todos os serviços. Se quiser, anexe
   fotos de referência. Clique em "Salvar e Gerar PDF".
   - **Cadastro rápido**: os botões "➕ Novo serviço" e "➕ Novo" (material) abrem
     um popup para cadastrar sem sair da tela de orçamento.
5. Na tela **Consultar**, os documentos ficam divididos em duas abas: **Orçamento**
   e **Ordem de Serviço**, cada uma com seus próprios filtros e status:
   - **Status de Orçamento**: Aguardando Aprovação (🟡) → Aprovado (🟢) ou Vencido (🔴).
     "Vencido" é calculado automaticamente quando a data de validade passa (e só se
     o orçamento ainda estiver "Aguardando Aprovação" — uma vez aprovado, nunca vence).
     O botão **"✅ Aprovar Orçamento"** marca o orçamento como aprovado e já leva
     direto para criar a Ordem de Serviço com os itens preenchidos.
   - **Status de Ordem de Serviço**: Nova → Aguardando aprovação → Em atendimento →
     Entregue, ou Reaberta se precisar retomar algo já entregue.
   - Em qualquer aba: **edite** (botão "✏️ Editar") ou **exclua** (botão "🗑️ Excluir",
     com popup de confirmação) qualquer documento.
6. O **Dashboard** (tela inicial) mostra Ordens de Serviço reabertas em destaque,
   as ordens em aberto mais próximas da entrega, e uma agenda dos próximos 7 dias
   — clique em qualquer uma para abrir os detalhes direto na tela Consultar.

## Sobre as fotos

As fotos anexadas ao orçamento/OS ficam no **Supabase Storage** (bucket `orcamento-fotos`),
não no banco de dados — isso evita estourar a cota de 500MB do Postgres free. O banco
guarda apenas a URL pública de cada foto. Elas não entram no PDF, servem só como
referência de consulta na tela.

## Sobre performance

As telas com muitos campos (como Orçamento) usam cache de 30 segundos
(`fetch_all_cached`) nas listas de prestador/clientes/serviços/materiais, porque o
Streamlit reexecuta o script inteiro a cada clique — sem cache, isso refazia as
mesmas consultas ao banco a cada interação. Se você cadastrar algo novo e ele não
aparecer imediatamente numa lista, aguarde alguns segundos ou recarregue a página.

