// Configurações de margem (espelho do produtos.json)
const CUSTOS = {
  comissao:  0.115,
  envio:     4.30,
  embalagem: 0.50,
  custo:     4.255,
};

function calcularMargem(preco) {
  return preco * (1 - CUSTOS.comissao) - CUSTOS.envio - CUSTOS.embalagem - CUSTOS.custo;
}

function formatarBRL(v) {
  if (v == null || isNaN(v)) return '—';
  const n = Number(v);
  return 'R$ ' + n.toFixed(2).replace('.', ',');
}

function formatarData(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

function badgeStatus(status) {
  const cls = status === 'active' ? 'status-ativo' : 'status-inativo';
  return `<span class="badge ${cls}">${status}</span>`;
}

async function carregarDados() {
  try {
    const res = await fetch('/api/dados');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const d = await res.json();
    renderizar(d);
  } catch (e) {
    console.error('Erro ao carregar dados:', e);
    document.getElementById('ultima-coleta').textContent = 'Erro ao carregar dados';
  }
}

function renderizar(d) {
  // ── Última coleta ────────────────────────────────────────────────────────
  const elColeta = document.getElementById('ultima-coleta');
  elColeta.textContent = d.ultima_coleta
    ? `Atualizado: ${formatarData(d.ultima_coleta)}`
    : 'Nunca coletado';

  // ── KPIs ─────────────────────────────────────────────────────────────────
  const vh = d.vendas_hoje || {};
  document.getElementById('kpi-receita').textContent   = formatarBRL(vh.receita || 0);
  document.getElementById('kpi-unidades').textContent  = vh.unidades || 0;

  const totalVisitas = (d.proprios || []).reduce((s, p) => s + (p.visitas_30d || 0), 0);
  document.getElementById('kpi-visitas').textContent = totalVisitas.toLocaleString('pt-BR');

  const proprios = d.proprios || [];
  const margens  = proprios.filter(p => p.preco).map(p => calcularMargem(p.preco));
  const margMedia = margens.length ? margens.reduce((a, b) => a + b, 0) / margens.length : 0;
  const elMargem  = document.getElementById('kpi-margem');
  elMargem.textContent = formatarBRL(margMedia);
  elMargem.className   = 'kpi-value ' + (margMedia >= 0 ? 'pos' : 'neg');

  const alertasAtivos = (d.alertas || []).filter(a => !a.enviado).length;
  document.getElementById('kpi-alertas').textContent = alertasAtivos || '0';

  // ── Histórico mensal ─────────────────────────────────────────────────────
  const tbHistorico = document.getElementById('tbody-historico');
  const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  tbHistorico.innerHTML = (d.historico_mensal || []).map(h => {
    const [ano, mes] = h.mes.split('-');
    const nomeMes = MESES[parseInt(mes) - 1] + '/' + ano.slice(2);
    return `<tr>
      <td>${nomeMes}</td>
      <td>${formatarBRL(h.receita)}</td>
      <td>${h.unidades}</td>
      <td>${h.pedidos}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="4" style="color:var(--text2)">Sem dados históricos</td></tr>';

  // ── Meus anúncios ────────────────────────────────────────────────────────
  const tbProprios = document.getElementById('tbody-proprios');
  tbProprios.innerHTML = proprios.map(p => {
    const margem = p.preco ? calcularMargem(p.preco) : null;
    const margemStr = margem != null
      ? `<span class="${margem >= 0 ? 'pos' : 'neg'}">${formatarBRL(margem)}</span>`
      : '—';
    return `<tr>
      <td>
        <div style="font-weight:600;font-size:0.82rem;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${p.titulo || p.item_id}
        </div>
        <div style="color:var(--text2);font-size:0.72rem">${p.item_id}</div>
      </td>
      <td>${formatarBRL(p.preco)}</td>
      <td>${(p.visitas_30d || 0).toLocaleString('pt-BR')}</td>
      <td>${p.total_vendido ?? '—'}</td>
      <td>${p.estoque_total ?? '—'}</td>
      <td>${margemStr}</td>
      <td>${badgeStatus(p.status || 'unknown')}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" style="color:var(--text2)">Sem dados coletados ainda</td></tr>';

  // ── Concorrentes ─────────────────────────────────────────────────────────
  const tbConc = document.getElementById('tbody-concorrentes');
  const meuMenor = proprios.length
    ? Math.min(...proprios.filter(p => p.preco).map(p => p.preco))
    : null;

  tbConc.innerHTML = (d.concorrentes || []).map((c, i) => {
    const delta = meuMenor != null && c.preco
      ? c.preco - meuMenor
      : null;
    const deltaStr = delta != null
      ? `<span class="${delta < 0 ? 'neg' : 'pos'}">${delta > 0 ? '+' : ''}${formatarBRL(delta)}</span>`
      : '—';
    const frete = c.frete_gratis ? '✅' : '—';
    return `<tr>
      <td style="color:var(--text2)">${c.posicao_busca || i + 1}</td>
      <td style="font-weight:500">${c.vendedor_nome || '—'}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:0.8rem">${c.titulo || '—'}</td>
      <td>${formatarBRL(c.preco)}</td>
      <td>${c.total_vendido ?? '—'}</td>
      <td>${c.reviews_nota ? c.reviews_nota.toFixed(1) + ' ★' : '—'}</td>
      <td style="text-align:center">${frete}</td>
      <td style="color:var(--text2);font-size:0.75rem">${c.termo_busca || '—'}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="8" style="color:var(--text2)">Sem concorrentes coletados ainda. Configure concorrentes.json ou aguarde a próxima busca automática.</td></tr>';

  // ── Pedidos recentes ──────────────────────────────────────────────────────
  const listaPedidos = document.getElementById('lista-pedidos');
  listaPedidos.innerHTML = (d.pedidos_recentes || []).map(p =>
    `<li class="pedido-item">
      <span class="pedido-data">${formatarData(p.date_created)}</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:0 0.5rem;font-size:0.8rem">${p.item_id}</span>
      <strong>${formatarBRL(p.total_amount)}</strong>
    </li>`
  ).join('') || '<li style="color:var(--text2);font-size:0.85rem;padding:0.5rem 0">Sem pedidos registrados</li>';

  // ── Alertas ───────────────────────────────────────────────────────────────
  const listaAlertas = document.getElementById('lista-alertas');
  const alertas = (d.alertas || []);
  if (alertas.length) {
    listaAlertas.innerHTML = alertas.map(a => {
      const cls = a.tipo ? a.tipo.toLowerCase() : '';
      return `<li class="alerta-item alerta-${cls}">${a.mensagem}</li>`;
    }).join('');
  } else {
    listaAlertas.innerHTML = '<li class="alerta-vazio">Nenhum alerta ativo</li>';
  }
}

// Carrega ao iniciar e a cada 5 minutos
carregarDados();
setInterval(carregarDados, 5 * 60 * 1000);
