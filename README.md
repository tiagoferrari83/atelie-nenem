# Ateliê - Sistema de Gestão

Sistema simples para gerenciar um ateliê de costura: cadastro de prestador de serviço,
clientes, serviços e matéria-prima, além de geração de orçamentos e ordens de serviço em PDF.

## Como rodar localmente

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

2. Copie o arquivo `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml`
   e preencha com a sua connection string real do Supabase (com a senha):
   ```
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

3. Rode o app:
   ```
   streamlit run app.py
   ```

## Deploy no Streamlit Community Cloud

1. Suba este projeto para um repositório no GitHub — **sem o arquivo `secrets.toml`**
   (ele já está no `.gitignore`, só o `.example` deve ir para o Git).
2. Acesse [share.streamlit.io](https://share.streamlit.io), conecte seu GitHub e
   selecione o repositório.
3. Em **Settings → Secrets** do próprio Streamlit Cloud, cole o conteúdo do seu
   `secrets.toml` real (com a senha do Supabase).
4. Deploy!

## Estrutura

- `app.py` — página inicial
- `database.py` — conexão com Supabase e criação das tabelas
- `pages/1_Prestador.py` — cadastro dos dados da empresa/ateliê (com logo)
- `pages/2_Clientes.py` — cadastro de clientes
- `pages/3_Servicos.py` — cadastro de serviços (por unidade, tempo ou metro)
- `pages/4_Materia_Prima.py` — cadastro de matéria-prima (por unidade, metro ou peso)
- `pages/5_Orcamento.py` — monta orçamento/ordem de serviço e gera o PDF
- `pdf_generator.py` — geração dos PDFs de orçamento/ordem de serviço

## Fluxo de uso

1. Cadastre o **Prestador de Serviço** (seus dados, aparecem no cabeçalho do PDF)
2. Cadastre **Clientes**
3. Cadastre **Serviços** e/ou **Matéria-Prima**
4. Na página **Orçamento**, escolha o cliente, adicione os itens desejados,
   defina se é Orçamento ou Ordem de Serviço, e clique em "Salvar e Gerar PDF"
