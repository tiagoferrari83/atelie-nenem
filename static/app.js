/**
 * Lógica principal da SPA do Ateliê (Alpine.js)
 * Cálculos de Orçamento e Ordem de Serviço em tempo real (0ms de latência).
 */

const UNIDADES_SERVICO = { unidade: "un.", tempo: "h", metro: "m" };
const UNIDADES_MATERIAL = { unidade: "un.", metro: "m", peso: "kg" };
const LABELS_SERVICO = {
  unidade: "Por unidade",
  tempo: "Por tempo (hora)",
  metro: "Por metro",
};
const LABELS_MEDIDA = {
  unidade: "Por unidade",
  metro: "Por metro",
  peso: "Por peso (kg)",
};
const LABELS_TIPO_MATERIAL = {
  tecido: "Tecido",
  aviamento: "Aviamento",
  outros: "Outros",
};
const LABELS_STATUS_OS = {
  nova: "Nova",
  aguardando_aprovacao: "Aguardando aprovação",
  em_atendimento: "Em atendimento",
  entregue: "Entregue",
  reaberta: "Reaberta",
};
const LABELS_STATUS_ORC = {
  aguardando_aprovacao: "Aguardando Aprovação",
  aprovado: "Aprovado",
  vencido: "Vencido",
};
const COMPLEXIDADE_ACRESCIMO = { 1: 0.0, 2: 0.1, 3: 0.2 };

function dataFuturaISO(dias = 7) {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return d.toISOString().slice(0, 10);
}

window.atelieApp = function () {
  return {
    // ── Autenticação & Estado Global ──
    token: localStorage.getItem("atelie_token") || "",
    userEmail: localStorage.getItem("atelie_email") || "",
    loginEmail: "",
    loginSenha: "",
    loginLoading: false,
    loginErro: "",

    carregando: false,
    salvando: false,
    page: "dashboard",
    menuMobileAberto: false,
    toast: { visivel: false, texto: "", tipo: "sucesso" },

    // ── Dados em Memória (carregados via /api/bootstrap) ──
    prestador: {
      nome: "",
      telefone: "",
      email: "",
      cnpj: "",
      clausulas: "",
      logo_base64: null,
    },
    clientes: [],
    servicos: [],
    materiais: [],
    dashboard: { reabertas: [], abertas: [], agenda: [] },
    documentos: [],
    documentosCarregados: false,

    // ── Filtros de Busca Instantânea ──
    buscaCliente: "",
    buscaServico: "",
    buscaMaterial: "",

    // ── Formulários de Cadastros Base ──
    novoCliente: { nome: "", telefone: "", email: "", endereco: "" },
    novoServico: { nome: "", tipo_cobranca: "unidade", valor: "" },
    novoMaterial: {
      nome: "",
      tipo_material: "tecido",
      tipo_medida: "metro",
      valor: "",
    },

    // ── Modais de Edição / Exclusão / Cadastro Rápido ──
    modal: {
      tipo: null, // 'edit_cliente' | 'del_cliente' | 'edit_servico' | 'edit_material' | 'rapido_servico' | 'rapido_material' | 'rapido_cliente' | 'del_doc'
      dados: {},
      vinculosCliente: [],
    },

    // ── Estado do Formulário de Orçamento ──
    orcForm: {
      editandoId: null,
      cliente_id: "",
      data_validade: dataFuturaISO(7),
      descricao_livre: "",
      tecidos: [],
      aviamentos: [],
      outros: [],
      servicos: [],
      fotosExistentes: [],
      novasFotos: [], // [{file, preview, name, pagina_inteira}]
      // Inputs temporários de adição por seção
      inTecido: { item_id: "", quantidade: 1, observacao: "" },
      inAviamento: { item_id: "", quantidade: 1, observacao: "" },
      inOutros: { item_id: "", quantidade: 1, observacao: "" },
      inServico: {
        item_id: "",
        complexidade: 1,
        quantidade: 1,
        tipo_desconto: "nenhum",
        valor_desconto: 0,
        motivo_desconto: "",
        observacao: "",
      },
    },

    // ── Estado do Formulário de Ordem de Serviço (OS) ──
    osForm: {
      editandoId: null,
      orcamento_origem_id: null,
      cliente_id: "",
      data_entrega: dataFuturaISO(7),
      observacoes: "",
      grupos: [], // [{servico: {...}, materiais: [...], inMatId: '', inMatQtd: 1}]
      fotosExistentes: [],
      novasFotos: [],
      inServico: {
        item_id: "",
        complexidade: 1,
        quantidade: 1,
        tipo_desconto: "nenhum",
        valor_desconto: 0,
        motivo_desconto: "",
        observacao: "",
      },
    },

    // ── Estado da Tela Consultar ──
    consultar: {
      aba: "orcamento", // 'orcamento' | 'ordem_servico'
      filtroCliente: "",
      filtroStatusOrc: "Todos",
      filtroStatusOs: "Todos",
      expandidos: {}, // {docId: true/false}
    },

    // ══════════════════════════════════════════════════════════════
    // INICIALIZAÇÃO E UTILITÁRIOS
    // ══════════════════════════════════════════════════════════════

    async init() {
      if (this.token) {
        await this.carregarBootstrap();
      }
    },

    mostrarToast(texto, tipo = "sucesso") {
      this.toast = { visivel: true, texto, tipo };
      setTimeout(() => {
        this.toast.visivel = false;
      }, 3800);
    },

    formatarMoeda(valor) {
      const n = Number(valor || 0);
      return n.toLocaleString("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    },

    normalizarTexto(txt) {
      return String(txt || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
    },

    filtrarListaCombo(opcoes, termo) {
      const b = this.normalizarTexto(termo);
      if (!b) return opcoes;
      return opcoes.filter((o) => this.normalizarTexto(o.label).includes(b));
    },

    opcoesClientes(incluirTodos = false) {
      const lista = this.clientes.map((c) => ({
        id: c.id,
        label: c.nome,
      }));
      if (incluirTodos) {
        return [{ id: "", label: "Todos os clientes" }, ...lista];
      }
      return lista;
    },

    labelClienteSelecionado(id, textoVazio = "-") {
      if (id === "" || id === null || id === undefined) return textoVazio;
      const c = this.clientes.find((x) => Number(x.id) === Number(id));
      return c ? c.nome : textoVazio;
    },

    opcoesServicos() {
      return this.servicos.map((s) => ({
        id: s.id,
        label: `${s.nome} (R$ ${this.formatarMoeda(s.valor)}/${UNIDADES_SERVICO[s.tipo_cobranca]})`,
      }));
    },

    labelServicoSelecionado(id) {
      if (id === "" || id === null || id === undefined) return "-";
      const s = this.servicos.find((x) => Number(x.id) === Number(id));
      if (!s) return "-";
      return `${s.nome} (R$ ${this.formatarMoeda(s.valor)}/${UNIDADES_SERVICO[s.tipo_cobranca]})`;
    },

    opcoesMateriaisPorTipo(tipo) {
      return this.materiais
        .filter((m) => (m.tipo_material || "outros") === tipo)
        .map((m) => ({
          id: m.id,
          label: `${m.nome} (R$ ${this.formatarMoeda(m.valor)}/${UNIDADES_MATERIAL[m.tipo_medida]})`,
        }));
    },

    opcoesTodosMateriais() {
      return this.materiais.map((m) => ({
        id: m.id,
        label: `${m.nome} (R$ ${this.formatarMoeda(m.valor)}/${UNIDADES_MATERIAL[m.tipo_medida]})`,
      }));
    },

    labelMaterialSelecionado(id) {
      if (id === "" || id === null || id === undefined) return "-";
      const m = this.materiais.find((x) => Number(x.id) === Number(id));
      if (!m) return "-";
      return `${m.nome} (R$ ${this.formatarMoeda(m.valor)}/${UNIDADES_MATERIAL[m.tipo_medida]})`;
    },

    opcoesComplexidade() {
      return [
        { id: 1, label: "1 — Simples (sem acréscimo)" },
        { id: 2, label: "2 — Médio (+10%)" },
        { id: 3, label: "3 — Complexo (+20%)" },
      ];
    },

    labelComplexidadeSelecionada(id) {
      const op = this.opcoesComplexidade().find(
        (x) => Number(x.id) === Number(id)
      );
      return op ? op.label : "1 — Simples (sem acréscimo)";
    },

    opcoesDesconto() {
      return [
        { id: "nenhum", label: "Sem desconto" },
        { id: "percentual", label: "Percentual (%)" },
        { id: "valor", label: "Valor (R$)" },
      ];
    },

    labelDescontoSelecionado(id) {
      const op = this.opcoesDesconto().find(
        (x) => String(x.id) === String(id)
      );
      return op ? op.label : "Sem desconto";
    },

    formatarQtd(qtd, descricao = "") {
      const n = Number(qtd || 0);
      const qStr = Number.isInteger(n)
        ? String(n)
        : n.toFixed(2).replace(/\.?0+$/, "").replace(".", ",");
      const partes = this.separarDescricaoUnidade(descricao);
      return partes.un ? `${qStr} ${partes.un}` : qStr;
    },

    separarDescricaoUnidade(descricao) {
      if (!descricao) return { nome: "", un: "" };
      const conhecidas = ["un.", "un", "m", "h", "kg"];
      for (const un of conhecidas) {
        const sufixo = `/${un}`;
        if (descricao.endsWith(sufixo)) {
          return {
            nome: descricao.slice(0, -sufixo.length).trim(),
            un,
          };
        }
      }
      return { nome: descricao.trim(), un: "" };
    },

    labelStatus(tipoOperacao, status) {
      return tipoOperacao === "orcamento"
        ? LABELS_STATUS_ORC[status] || status
        : LABELS_STATUS_OS[status] || status;
    },

    corStatusBadge(status) {
      const map = {
        nova: "bg-neutral-800 text-neutral-200 border-neutral-700",
        aguardando_aprovacao: "bg-amber-950/80 text-amber-300 border-amber-800",
        em_atendimento: "bg-orange-950/80 text-orange-300 border-orange-800",
        entregue: "bg-emerald-950/80 text-emerald-300 border-emerald-800",
        aprovado: "bg-emerald-950/80 text-emerald-300 border-emerald-800",
        reaberta: "bg-rose-950/80 text-rose-300 border-rose-800",
        vencido: "bg-rose-950/80 text-rose-300 border-rose-800",
      };
      return map[status] || "bg-neutral-800 text-neutral-300 border-neutral-700";
    },

    async apiFetch(url, options = {}) {
      const headers = options.headers || {};
      if (this.token) {
        headers["Authorization"] = `Bearer ${this.token}`;
      }
      if (options.body && !(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
      }
      const resp = await fetch(url, { ...options, headers });
      if (resp.status === 401) {
        this.fazerLogout();
        throw new Error("Sessão expirada. Faça login novamente.");
      }
      if (!resp.ok) {
        let msg = "Erro na operação.";
        try {
          const err = await resp.json();
          msg = err.detail || msg;
        } catch (_) {}
        throw new Error(msg);
      }
      return resp.json();
    },

    // ══════════════════════════════════════════════════════════════
    // AUTENTICAÇÃO E CARGA INICIAL
    // ══════════════════════════════════════════════════════════════

    async fazerLogin() {
      this.loginErro = "";
      this.loginLoading = true;
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: this.loginEmail,
            senha: this.loginSenha,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "E-mail ou senha incorretos.");
        }
        this.token = data.access_token;
        this.userEmail = data.email;
        localStorage.setItem("atelie_token", this.token);
        localStorage.setItem("atelie_email", this.userEmail);
        this.loginSenha = "";
        await this.carregarBootstrap();
      } catch (e) {
        this.loginErro = e.message;
      } finally {
        this.loginLoading = false;
      }
    },

    fazerLogout() {
      this.token = "";
      this.userEmail = "";
      localStorage.removeItem("atelie_token");
      localStorage.removeItem("atelie_email");
    },

    async carregarBootstrap() {
      this.carregando = true;
      try {
        const data = await this.apiFetch("/api/bootstrap");
        this.userEmail = data.user_email || this.userEmail;
        if (data.prestador) {
          this.prestador = data.prestador;
        }
        this.clientes = data.clientes || [];
        this.servicos = data.servicos || [];
        this.materiais = data.materiais || [];
        this.dashboard = data.dashboard || {
          reabertas: [],
          abertas: [],
          agenda: [],
        };
        this.sincronizarDefaultsFormularios();
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.carregando = false;
      }
    },

    sincronizarDefaultsFormularios() {
      // Campos de Clientes, Materiais e Serviços permanecem vazios ("-") até o usuário selecionar.
    },

    async navegarPara(destino, opcoes = {}) {
      this.menuMobileAberto = false;
      if (destino === "orcamento" && !opcoes.manterEdicao) {
        this.resetarOrcamento();
      }
      if (destino === "os" && !opcoes.manterEdicao) {
        this.resetarOS();
      }
      this.page = destino;
      if (destino === "consultar") {
        await this.carregarDocumentos();
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    },

    // ══════════════════════════════════════════════════════════════
    // PRESTADOR, CLIENTES, SERVIÇOS E MATÉRIA-PRIMA
    // ══════════════════════════════════════════════════════════════

    aoSelecionarLogoPrestador(event) {
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        this.prestador.logo_base64 = e.target.result;
      };
      reader.readAsDataURL(file);
    },

    async salvarPrestador() {
      if (!this.prestador.nome.trim()) {
        this.mostrarToast("O nome do prestador é obrigatório.", "erro");
        return;
      }
      this.salvando = true;
      try {
        await this.apiFetch("/api/prestador", {
          method: "POST",
          body: JSON.stringify(this.prestador),
        });
        this.mostrarToast("Dados do prestador salvos com sucesso!");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    get clientesFiltrados() {
      const b = this.buscaCliente.trim().toLowerCase();
      if (!b) return this.clientes;
      return this.clientes.filter(
        (c) =>
          (c.nome || "").toLowerCase().includes(b) ||
          (c.telefone || "").toLowerCase().includes(b) ||
          (c.email || "").toLowerCase().includes(b)
      );
    },

    async cadastrarCliente(rapido = false) {
      const alvo = rapido ? this.modal.dados : this.novoCliente;
      if (!alvo.nome || !alvo.nome.trim()) {
        this.mostrarToast("O nome do cliente é obrigatório.", "erro");
        return;
      }
      this.salvando = true;
      try {
        const res = await this.apiFetch("/api/clientes", {
          method: "POST",
          body: JSON.stringify(alvo),
        });
        await this.carregarBootstrap();
        if (rapido) {
          if (this.page === "orcamento") this.orcForm.cliente_id = res.id;
          if (this.page === "os") this.osForm.cliente_id = res.id;
          this.modal.tipo = null;
        } else {
          this.novoCliente = {
            nome: "",
            telefone: "",
            email: "",
            endereco: "",
          };
        }
        this.mostrarToast("Cliente cadastrado com sucesso!");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    abrirEdicaoCliente(c) {
      this.modal = {
        tipo: "edit_cliente",
        dados: { ...c },
        vinculosCliente: [],
      };
    },

    async salvarEdicaoCliente() {
      this.salvando = true;
      try {
        await this.apiFetch(`/api/clientes/${this.modal.dados.id}`, {
          method: "PUT",
          body: JSON.stringify(this.modal.dados),
        });
        this.modal.tipo = null;
        await this.carregarBootstrap();
        this.mostrarToast("Cliente atualizado!");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    async abrirExclusaoCliente(c) {
      try {
        const res = await this.apiFetch(`/api/clientes/${c.id}/vinculos`);
        this.modal = {
          tipo: "del_cliente",
          dados: { ...c },
          vinculosCliente: res.documentos || [],
        };
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      }
    },

    async confirmarExclusaoCliente() {
      this.salvando = true;
      try {
        await this.apiFetch(`/api/clientes/${this.modal.dados.id}`, {
          method: "DELETE",
        });
        this.modal.tipo = null;
        await this.carregarBootstrap();
        this.mostrarToast("Cliente excluído com sucesso.");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    // ── Serviços ──
    get servicosFiltrados() {
      const b = this.buscaServico.trim().toLowerCase();
      if (!b) return this.servicos;
      return this.servicos.filter((s) =>
        (s.nome || "").toLowerCase().includes(b)
      );
    },

    async cadastrarServico(rapido = false) {
      const alvo = rapido ? this.modal.dados : this.novoServico;
      if (!alvo.nome || !alvo.nome.trim()) {
        this.mostrarToast("Informe o nome do serviço.", "erro");
        return;
      }
      this.salvando = true;
      try {
        const res = await this.apiFetch("/api/servicos", {
          method: "POST",
          body: JSON.stringify({
            nome: alvo.nome,
            tipo_cobranca: alvo.tipo_cobranca || "unidade",
            valor: Number(alvo.valor || 0),
          }),
        });
        await this.carregarBootstrap();
        if (rapido) {
          this.orcForm.inServico.item_id = res.id;
          this.osForm.inServico.item_id = res.id;
          this.modal.tipo = null;
        } else {
          this.novoServico = { nome: "", tipo_cobranca: "unidade", valor: "" };
        }
        this.mostrarToast("Serviço cadastrado!");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    abrirEdicaoServico(s) {
      this.modal = { tipo: "edit_servico", dados: { ...s } };
    },

    async salvarEdicaoServico() {
      this.salvando = true;
      try {
        await this.apiFetch(`/api/servicos/${this.modal.dados.id}`, {
          method: "PUT",
          body: JSON.stringify({
            nome: this.modal.dados.nome,
            tipo_cobranca: this.modal.dados.tipo_cobranca,
            valor: Number(this.modal.dados.valor || 0),
          }),
        });
        this.modal.tipo = null;
        await this.carregarBootstrap();
        this.mostrarToast("Serviço atualizado!");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    async excluirServico(id) {
      if (!confirm("Deseja excluir este serviço?")) return;
      try {
        await this.apiFetch(`/api/servicos/${id}`, { method: "DELETE" });
        await this.carregarBootstrap();
        this.mostrarToast("Serviço excluído.");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      }
    },

    // ── Matéria-Prima ──
    materiaisPorTipo(tipo) {
      const b = this.buscaMaterial.trim().toLowerCase();
      return this.materiais.filter(
        (m) =>
          (m.tipo_material || "outros") === tipo &&
          (!b || (m.nome || "").toLowerCase().includes(b))
      );
    },

    async cadastrarMaterial(rapido = false) {
      const alvo = rapido ? this.modal.dados : this.novoMaterial;
      if (!alvo.nome || !alvo.nome.trim()) {
        this.mostrarToast("Informe o nome do material.", "erro");
        return;
      }
      this.salvando = true;
      try {
        const res = await this.apiFetch("/api/materiais", {
          method: "POST",
          body: JSON.stringify({
            nome: alvo.nome,
            tipo_material: alvo.tipo_material || "outros",
            tipo_medida: alvo.tipo_medida || "unidade",
            valor: Number(alvo.valor || 0),
          }),
        });
        await this.carregarBootstrap();
        if (rapido) {
          const tm = alvo.tipo_material || "outros";
          if (tm === "tecido") this.orcForm.inTecido.item_id = res.id;
          else if (tm === "aviamento")
            this.orcForm.inAviamento.item_id = res.id;
          else this.orcForm.inOutros.item_id = res.id;
          this.modal.tipo = null;
        } else {
          this.novoMaterial = {
            nome: "",
            tipo_material: "tecido",
            tipo_medida: "metro",
            valor: "",
          };
        }
        this.mostrarToast("Material cadastrado!");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    abrirEdicaoMaterial(m) {
      this.modal = { tipo: "edit_material", dados: { ...m } };
    },

    async salvarEdicaoMaterial() {
      this.salvando = true;
      try {
        await this.apiFetch(`/api/materiais/${this.modal.dados.id}`, {
          method: "PUT",
          body: JSON.stringify({
            nome: this.modal.dados.nome,
            tipo_material: this.modal.dados.tipo_material,
            tipo_medida: this.modal.dados.tipo_medida,
            valor: Number(this.modal.dados.valor || 0),
          }),
        });
        this.modal.tipo = null;
        await this.carregarBootstrap();
        this.mostrarToast("Material atualizado!");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    async excluirMaterial(id) {
      if (!confirm("Deseja excluir este material?")) return;
      try {
        await this.apiFetch(`/api/materiais/${id}`, { method: "DELETE" });
        await this.carregarBootstrap();
        this.mostrarToast("Material excluído.");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      }
    },

    // ══════════════════════════════════════════════════════════════
    // CÁLCULOS INSTANTÂNEOS DE ORÇAMENTO E OS (0ms no navegador)
    // ══════════════════════════════════════════════════════════════

    precoServicoComComplexidade(servicoId, nivelComplexidade) {
      const s = this.servicos.find((x) => Number(x.id) === Number(servicoId));
      if (!s) return { base: 0, final: 0, un: "un." };
      const base = Number(s.valor || 0);
      const acrescimo = COMPLEXIDADE_ACRESCIMO[Number(nivelComplexidade)] || 0;
      const final = Math.round(base * (1 + acrescimo) * 100) / 100;
      const un = UNIDADES_SERVICO[s.tipo_cobranca] || "un.";
      return { base, final, un, nome: s.nome };
    },

    adicionarMaterialOrcamento(secao) {
      const mapaInput = {
        tecidos: "inTecido",
        aviamentos: "inAviamento",
        outros: "inOutros",
      };
      const inp = this.orcForm[mapaInput[secao]];
      const qtd = Number(inp.quantidade || 0);
      if (qtd <= 0) {
        this.mostrarToast("Informe uma quantidade maior que zero.", "erro");
        return;
      }
      const m = this.materiais.find((x) => Number(x.id) === Number(inp.item_id));
      if (!m) {
        this.mostrarToast("Selecione um material válido.", "erro");
        return;
      }
      const un = UNIDADES_MATERIAL[m.tipo_medida] || "un.";
      const vu = Number(m.valor || 0);
      const vt = Math.round(vu * qtd * 100) / 100;
      this.orcForm[secao].push({
        item_id: m.id,
        descricao: `${m.nome}/${un}`,
        quantidade: qtd,
        valor_unitario: vu,
        valor_total: vt,
        observacao_item: (inp.observacao || "").trim(),
      });
      inp.item_id = "";
      inp.quantidade = 1;
      inp.observacao = "";
    },

    _montarObjetoServico(inp) {
      const qtd = Number(inp.quantidade || 0);
      if (qtd <= 0) {
        this.mostrarToast("Informe uma quantidade maior que zero.", "erro");
        return null;
      }
      const info = this.precoServicoComComplexidade(
        inp.item_id,
        inp.complexidade
      );
      if (!info.nome) {
        this.mostrarToast("Selecione um serviço válido.", "erro");
        return null;
      }
      const totalBruto = Math.round(info.final * qtd * 100) / 100;
      let descontoCalc = 0.0;
      let tipoDescontoBd = null;
      const valDesc = Number(inp.valor_desconto || 0);

      if (inp.tipo_desconto === "percentual" && valDesc > 0) {
        descontoCalc = Math.round(totalBruto * (valDesc / 100.0) * 100) / 100;
        tipoDescontoBd = "percentual";
      } else if (inp.tipo_desconto === "valor" && valDesc > 0) {
        descontoCalc = Math.round(Math.min(valDesc, totalBruto) * 100) / 100;
        tipoDescontoBd = "valor";
      }

      return {
        item_id: Number(inp.item_id),
        descricao: `${info.nome}/${info.un}`,
        quantidade: qtd,
        valor_unitario: info.final,
        valor_total: totalBruto,
        observacao_item: (inp.observacao || "").trim(),
        tipo_desconto: tipoDescontoBd,
        valor_desconto: tipoDescontoBd ? valDesc : 0.0,
        motivo_desconto: tipoDescontoBd
          ? (inp.motivo_desconto || "").trim() || "Desconto"
          : "",
        desconto_calculado: descontoCalc,
      };
    },

    adicionarServicoOrcamento() {
      const srv = this._montarObjetoServico(this.orcForm.inServico);
      if (!srv) return;
      this.orcForm.servicos.push(srv);
      this.orcForm.inServico.item_id = "";
      this.orcForm.inServico.complexidade = 1;
      this.orcForm.inServico.quantidade = 1;
      this.orcForm.inServico.tipo_desconto = "nenhum";
      this.orcForm.inServico.valor_desconto = 0;
      this.orcForm.inServico.motivo_desconto = "";
      this.orcForm.inServico.observacao = "";
    },

    get totaisOrcamento() {
      const soma = (arr) =>
        arr.reduce((acc, i) => acc + Number(i.valor_total || 0), 0);
      const subtotal =
        soma(this.orcForm.tecidos) +
        soma(this.orcForm.aviamentos) +
        soma(this.orcForm.outros) +
        soma(this.orcForm.servicos);
      const descontos = this.orcForm.servicos.reduce(
        (acc, s) => acc + Number(s.desconto_calculado || 0),
        0
      );
      return {
        subtotal: Math.round(subtotal * 100) / 100,
        descontos: Math.round(descontos * 100) / 100,
        liquido: Math.max(0, Math.round((subtotal - descontos) * 100) / 100),
        temItens:
          this.orcForm.tecidos.length +
            this.orcForm.aviamentos.length +
            this.orcForm.outros.length +
            this.orcForm.servicos.length >
          0,
      };
    },

    adicionarServicoOS() {
      const srv = this._montarObjetoServico(this.osForm.inServico);
      if (!srv) return;
      this.osForm.grupos.push({
        servico: srv,
        materiais: [],
        inMatId: "",
        inMatQtd: 1,
      });
      this.osForm.inServico.item_id = "";
      this.osForm.inServico.complexidade = 1;
      this.osForm.inServico.quantidade = 1;
      this.osForm.inServico.tipo_desconto = "nenhum";
      this.osForm.inServico.valor_desconto = 0;
      this.osForm.inServico.motivo_desconto = "";
      this.osForm.inServico.observacao = "";
    },

    adicionarMaterialNoGrupoOS(idxGrupo) {
      const g = this.osForm.grupos[idxGrupo];
      const qtd = Number(g.inMatQtd || 0);
      if (qtd <= 0) {
        this.mostrarToast("Informe uma quantidade maior que zero.", "erro");
        return;
      }
      const m = this.materiais.find((x) => Number(x.id) === Number(g.inMatId));
      if (!m) {
        this.mostrarToast("Selecione um material.", "erro");
        return;
      }
      const un = UNIDADES_MATERIAL[m.tipo_medida] || "un.";
      const vu = Number(m.valor || 0);
      g.materiais.push({
        item_id: m.id,
        descricao: `${m.nome}/${un}`,
        quantidade: qtd,
        valor_unitario: vu,
        valor_total: Math.round(vu * qtd * 100) / 100,
      });
      g.inMatId = "";
      g.inMatQtd = 1;
    },

    subtotalGrupoOS(grupo) {
      const sVal = Number(grupo.servico.valor_total || 0);
      const mVal = (grupo.materiais || []).reduce(
        (acc, m) => acc + Number(m.valor_total || 0),
        0
      );
      return Math.round((sVal + mVal) * 100) / 100;
    },

    get totaisOS() {
      const subtotal = this.osForm.grupos.reduce(
        (acc, g) => acc + this.subtotalGrupoOS(g),
        0
      );
      const descontos = this.osForm.grupos.reduce(
        (acc, g) => acc + Number(g.servico.desconto_calculado || 0),
        0
      );
      return {
        subtotal: Math.round(subtotal * 100) / 100,
        descontos: Math.round(descontos * 100) / 100,
        liquido: Math.max(0, Math.round((subtotal - descontos) * 100) / 100),
      };
    },

    // ── Fotos nos Formulários ──
    selecionarNovasFotos(event, alvoForm) {
      const files = Array.from(event.target.files || []);
      for (const file of files) {
        const preview = URL.createObjectURL(file);
        alvoForm.novasFotos.push({
          file,
          preview,
          name: file.name,
          pagina_inteira: false,
        });
      }
      event.target.value = "";
    },

    removerNovaFoto(alvoForm, idx) {
      alvoForm.novasFotos.splice(idx, 1);
    },

    async excluirFotoExistente(alvoForm, fotoId, idx) {
      try {
        await this.apiFetch(`/api/fotos/${fotoId}`, { method: "DELETE" });
        alvoForm.fotosExistentes.splice(idx, 1);
        this.mostrarToast("Foto removida.");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      }
    },

    resetarOrcamento() {
      this.orcForm.editandoId = null;
      this.orcForm.cliente_id = "";
      this.orcForm.data_validade = dataFuturaISO(7);
      this.orcForm.descricao_livre = "";
      this.orcForm.tecidos = [];
      this.orcForm.aviamentos = [];
      this.orcForm.outros = [];
      this.orcForm.servicos = [];
      this.orcForm.fotosExistentes = [];
      this.orcForm.novasFotos = [];
      this.orcForm.inTecido = { item_id: "", quantidade: 1, observacao: "" };
      this.orcForm.inAviamento = { item_id: "", quantidade: 1, observacao: "" };
      this.orcForm.inOutros = { item_id: "", quantidade: 1, observacao: "" };
      this.orcForm.inServico = {
        item_id: "",
        complexidade: 1,
        quantidade: 1,
        tipo_desconto: "nenhum",
        valor_desconto: 0,
        motivo_desconto: "",
        observacao: "",
      };
    },

    resetarOS() {
      this.osForm.editandoId = null;
      this.osForm.orcamento_origem_id = null;
      this.osForm.cliente_id = "";
      this.osForm.data_entrega = dataFuturaISO(7);
      this.osForm.observacoes = "";
      this.osForm.grupos = [];
      this.osForm.fotosExistentes = [];
      this.osForm.novasFotos = [];
      this.osForm.inServico = {
        item_id: "",
        complexidade: 1,
        quantidade: 1,
        tipo_desconto: "nenhum",
        valor_desconto: 0,
        motivo_desconto: "",
        observacao: "",
      };
    },

    // ── Salvar Orçamento / OS e Baixar PDF ──
    async salvarOrcamentoEGerarPDF() {
      if (!this.orcForm.cliente_id) {
        this.mostrarToast("Selecione um cliente.", "erro");
        return;
      }
      if (!this.totaisOrcamento.temItens) {
        this.mostrarToast("Adicione pelo menos um item ao orçamento.", "erro");
        return;
      }
      this.salvando = true;
      try {
        const fotosCfg = {};
        for (const f of this.orcForm.fotosExistentes) {
          fotosCfg[f.id] = Boolean(f.pagina_inteira);
        }
        const payload = {
          tipo_operacao: "orcamento",
          cliente_id: Number(this.orcForm.cliente_id),
          tipo_pedido: "confeccao",
          data_validade: this.orcForm.data_validade,
          descricao_livre: this.orcForm.descricao_livre,
          secoes: {
            tecidos: this.orcForm.tecidos,
            aviamentos: this.orcForm.aviamentos,
            outros: this.orcForm.outros,
            servicos: this.orcForm.servicos,
          },
          fotos_cfg: fotosCfg,
        };

        let docId = this.orcForm.editandoId;
        if (docId) {
          await this.apiFetch(`/api/documentos/${docId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
        } else {
          const res = await this.apiFetch("/api/documentos", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          docId = res.id;
        }

        if (this.orcForm.novasFotos.length > 0) {
          await this._enviarNovasFotos(docId, this.orcForm.novasFotos);
        }

        this.mostrarToast("Orçamento salvo! Baixando PDF...");
        this.baixarPDF(docId);
        this.resetarOrcamento();
        await this.carregarBootstrap();
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    async salvarOSEGerarPDF() {
      if (!this.osForm.cliente_id) {
        this.mostrarToast("Selecione um cliente.", "erro");
        return;
      }
      if (this.osForm.grupos.length === 0) {
        this.mostrarToast("Adicione pelo menos um serviço à OS.", "erro");
        return;
      }
      this.salvando = true;
      try {
        const payload = {
          tipo_operacao: "ordem_servico",
          cliente_id: Number(this.osForm.cliente_id),
          tipo_pedido: "confeccao",
          data_entrega: this.osForm.data_entrega,
          observacoes: this.osForm.observacoes,
          orcamento_origem_id: this.osForm.orcamento_origem_id,
          grupos: this.osForm.grupos.map((g) => ({
            servico: g.servico,
            materiais: g.materiais,
          })),
        };

        let docId = this.osForm.editandoId;
        if (docId) {
          await this.apiFetch(`/api/documentos/${docId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
        } else {
          const res = await this.apiFetch("/api/documentos", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          docId = res.id;
        }

        if (this.osForm.novasFotos.length > 0) {
          await this._enviarNovasFotos(docId, this.osForm.novasFotos);
        }

        this.mostrarToast("Ordem de Serviço salva! Baixando PDF...");
        this.baixarPDF(docId);
        this.resetarOS();
        await this.carregarBootstrap();
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    async _enviarNovasFotos(docId, listaNovasFotos) {
      const fd = new FormData();
      const flags = [];
      for (const item of listaNovasFotos) {
        fd.append("files", item.file);
        flags.push(item.pagina_inteira ? "1" : "0");
      }
      fd.append("paginas_inteiras", flags.join(","));
      await this.apiFetch(`/api/documentos/${docId}/fotos`, {
        method: "POST",
        body: fd,
      });
    },

    baixarPDF(docId) {
      const url = `/api/documentos/${docId}/pdf?token=${encodeURIComponent(
        this.token
      )}`;
      window.open(url, "_blank");
    },

    // ══════════════════════════════════════════════════════════════
    // TELA CONSULTAR / EDIÇÃO / APROVAR ORÇAMENTO → GERAR OS
    // ══════════════════════════════════════════════════════════════

    async carregarDocumentos() {
      this.carregando = true;
      try {
        const res = await this.apiFetch("/api/documentos");
        this.documentos = res.documentos || [];
        this.documentosCarregados = true;
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.carregando = false;
      }
    },

    async abrirDocumentoNoConsultar(docId, tipoOperacao) {
      this.consultar.aba = tipoOperacao;
      this.consultar.filtroCliente = "";
      this.consultar.filtroStatusOrc = "Todos";
      this.consultar.filtroStatusOs = "Todos";
      this.consultar.expandidos = { [docId]: true };
      await this.navegarPara("consultar");
    },

    get orcamentosFiltrados() {
      return this.documentos.filter((d) => {
        if (d.tipo_operacao !== "orcamento") return false;
        if (
          this.consultar.filtroCliente &&
          Number(d.cliente_id) !== Number(this.consultar.filtroCliente)
        )
          return false;
        if (
          this.consultar.filtroStatusOrc !== "Todos" &&
          d.status !== this.consultar.filtroStatusOrc
        )
          return false;
        return true;
      });
    },

    get ordensFiltradas() {
      return this.documentos.filter((d) => {
        if (d.tipo_operacao !== "ordem_servico") return false;
        if (
          this.consultar.filtroCliente &&
          Number(d.cliente_id) !== Number(this.consultar.filtroCliente)
        )
          return false;
        if (
          this.consultar.filtroStatusOs !== "Todos" &&
          d.status !== this.consultar.filtroStatusOs
        )
          return false;
        return true;
      });
    },

    async alterarStatusDocumento(doc, novoStatus) {
      try {
        await this.apiFetch(`/api/documentos/${doc.id}/status`, {
          method: "PATCH",
          body: JSON.stringify({ status: novoStatus }),
        });
        doc.status = novoStatus;
        await this.carregarBootstrap();
        this.mostrarToast("Status atualizado!");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      }
    },

    editarDocumento(doc) {
      if (doc.tipo_operacao === "orcamento") {
        this.orcForm.editandoId = doc.id;
        this.orcForm.cliente_id = doc.cliente_id;
        this.orcForm.data_validade = doc.data_validade_iso || dataFuturaISO(7);
        this.orcForm.descricao_livre = doc.descricao_livre || "";
        this.orcForm.tecidos = JSON.parse(
          JSON.stringify(doc.secoes?.tecidos || [])
        );
        this.orcForm.aviamentos = JSON.parse(
          JSON.stringify(doc.secoes?.aviamentos || [])
        );
        this.orcForm.outros = JSON.parse(
          JSON.stringify(doc.secoes?.outros || [])
        );
        this.orcForm.servicos = JSON.parse(
          JSON.stringify(doc.secoes?.servicos || [])
        );
        this.orcForm.fotosExistentes = JSON.parse(
          JSON.stringify(doc.fotos || [])
        );
        this.orcForm.novasFotos = [];
        this.orcForm.inTecido = { item_id: "", quantidade: 1, observacao: "" };
        this.orcForm.inAviamento = { item_id: "", quantidade: 1, observacao: "" };
        this.orcForm.inOutros = { item_id: "", quantidade: 1, observacao: "" };
        this.orcForm.inServico = {
          item_id: "",
          complexidade: 1,
          quantidade: 1,
          tipo_desconto: "nenhum",
          valor_desconto: 0,
          motivo_desconto: "",
          observacao: "",
        };
        this.navegarPara("orcamento", { manterEdicao: true });
      } else {
        this.osForm.editandoId = doc.id;
        this.osForm.orcamento_origem_id = doc.orcamento_origem_id || null;
        this.osForm.cliente_id = doc.cliente_id;
        this.osForm.data_entrega = doc.data_entrega_iso || dataFuturaISO(7);
        this.osForm.observacoes = doc.observacoes || "";
        this.osForm.grupos = (doc.grupos || []).map((g) => ({
          servico: JSON.parse(JSON.stringify(g.servico)),
          materiais: JSON.parse(JSON.stringify(g.materiais || [])),
          inMatId: "",
          inMatQtd: 1,
        }));
        this.osForm.fotosExistentes = JSON.parse(
          JSON.stringify(doc.fotos || [])
        );
        this.osForm.novasFotos = [];
        this.osForm.inServico = {
          item_id: "",
          complexidade: 1,
          quantidade: 1,
          tipo_desconto: "nenhum",
          valor_desconto: 0,
          motivo_desconto: "",
          observacao: "",
        };
        this.navegarPara("os", { manterEdicao: true });
      }
    },

    aprovarOrcamentoEGerarOS(doc) {
      const matDefault = this.materiais.length > 0 ? this.materiais[0].id : "";
      this.resetarOS();
      this.osForm.orcamento_origem_id = doc.id;
      this.osForm.cliente_id = doc.cliente_id;
      this.osForm.observacoes = doc.descricao_livre || doc.observacoes || "";

      const todosMateriais = [
        ...(doc.secoes?.tecidos || []),
        ...(doc.secoes?.aviamentos || []),
        ...(doc.secoes?.outros || []),
      ];
      const servicosOrc = doc.secoes?.servicos || [];

      this.osForm.grupos = servicosOrc.map((s, idx) => ({
        servico: JSON.parse(JSON.stringify(s)),
        materiais:
          idx === 0 ? JSON.parse(JSON.stringify(todosMateriais)) : [],
        inMatId: matDefault,
        inMatQtd: 1,
      }));

      this.navegarPara("os", { manterEdicao: true });
      this.mostrarToast(
        `Itens do Orçamento #${doc.id} carregados na nova Ordem de Serviço!`
      );
    },

    confirmarExclusaoDocumento(doc) {
      this.modal = { tipo: "del_doc", dados: doc };
    },

    async executarExclusaoDocumento() {
      const doc = this.modal.dados;
      this.salvando = true;
      try {
        await this.apiFetch(`/api/documentos/${doc.id}`, { method: "DELETE" });
        this.modal.tipo = null;
        await this.carregarDocumentos();
        await this.carregarBootstrap();
        this.mostrarToast("Documento excluído com sucesso.");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      } finally {
        this.salvando = false;
      }
    },

    async excluirFotoNoConsultar(doc, fotoId, idx) {
      try {
        await this.apiFetch(`/api/fotos/${fotoId}`, { method: "DELETE" });
        doc.fotos.splice(idx, 1);
        this.mostrarToast("Foto excluída.");
      } catch (e) {
        this.mostrarToast(e.message, "erro");
      }
    },
  };
};
