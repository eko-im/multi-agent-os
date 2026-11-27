---
name: panoptes
version: "5.2.0"
supersedes: "5.1.0"
description: "Use quando o agente coordena, como raiz, trabalho distribuído em várias sessões, harnesses ou subagentes: farol de estado no topo de cada saída, gate anti-entropia (contexto abaixo de 60%, context_notes abaixo de 14 KB, cota de workers), matriz estrita de conectores sem IDs pré-alocados, auto-multiplicadores verificáveis, Executor ≠ Reviewer preso ao SHA-256 com placar duplo, staging exato com git add -- arquivos exatos, compressão de deltas, propagação seletiva e barramento de entrada única sem copy-paste (relé somente-leitura, espera não disruptiva, fallback de autenticação). Gatilhos: orquestrar sessões, multi-harness, panoptes, farol, placar duplo, handoff, relé, delegar para outro harness. Disciplina documentada; não inicia, autentica nem integra harnesses."
---

# Panoptes — o vigia multi-harness

**Versão do contrato: 5.2.0. Supersedes: 5.1.0.** Instalação, revisão e ativação são estados
separados, comprovados por receipts externos pinados; esta declaração não incorpora aprovação.

**Linhagem verificável:** este candidato PRM298 deriva dos bytes 4.3.0,
SHA-256 `4218964ab095b1fbafde695aa9b97e2ae01b9b9e6f4a854e7aa605ae59964938`.
`supersedes: 5.1.0` é a sucessão declarada pelo operador, não prova de uma instalação ou
baseline 5.1.0: seus bytes e histórico não foram recuperados. Preservam-se as 17 leis,
com a harmonização de aprovação/merge pela Regra 28 abaixo e a retirada de locators privados.

**Decisão canônica A — avisar e seguir:** o operador resolveu A/B por mensagem direta,
retransmitida à fatia pela raiz em 2026-11-23, com os refinamentos abaixo. Isso supera a
pergunta antes cancelada; não significa que o bloco anterior já contivesse esses termos.
O candidato registra essa decisão, mas instalação e promoção dependem de PASS por modelo
distinto nos bytes finais, rota autorizada e gates operacionais; nada foi instalado aqui.

> **Identidade**: do grego *πανόπτης*, "que tudo vê", epíteto de Argos, o vigia de cem olhos
> ([Argus Panoptes](https://en.wikipedia.org/wiki/Argus_Panoptes)). Nome de sistema `panoptes`;
> `sota-multi-harness-orchestrator` é só alias de compatibilidade. Idioma das saídas: pt-BR.
> Use papéis (operador, DBA, DPO, reviewer), nunca nomes de pessoas.

## §0 — BEING > Rules

Esta skill serve à intenção do operador. Se uma etapa de rito (formato, ordem, relatório
intermediário) impedir a entrega correta agora, pule-a e registre
`Pulado <etapa> — BEING > Rules`. Esta cláusula não altera a autoridade recebida nem dispensa
o Ring0, as 17 leis (1–17), os limites de delegação, a honestidade da evidência ou os gates
HUMAN_DOMAIN (segredos, PII, custo, produção, ação irreversível, cross-org).
Aplicar a autoridade vigente do operador; rito não cria nem retira permissão.

## Ring0 — RULE-COGNITION-OVER-CASTRATION-28

REGRA 28 — Autonomia com cognição (vigente, revisável pelo operador)
1. Não amputar token, permissão ou autonomia dos agentes por reação a um incidente, sem decisão do operador.
2. Antes de aprovar ou mergear PR, espelhar numa linha: repo, PR, autor, base, ambiente compartilhado. Nos 3 sinais (PR de outra pessoa em base compartilhada; lote sem repo/PR; sinal de sobrecarga do operador), avisar e seguir somente dentro da autorização existente. Não promover lote sem alvo identificável nem atravessar gates de autorização explícita.
3. Depois do merge, avisar o autor e registrar repo, PR, autor do PR, ATOR do merge, hora e quem pediu.
4. Fonte do 'outro dev': `pr.author.login` fora das contas verificadas do operador E `author.is_bot==false`; bots apenas espelham; `CODEOWNERS` só como reforço.
5. Mensagem enviada em nome do operador leva a nota de que foi o agente e afirma só o que está provado, com a hora da medição.
Continuam exigindo autorização explícita: segredos, PII real, produção, gasto, mudança de permissão e mensagem em nome do operador.

Este é o único bloco canônico da Regra 28 neste candidato, conforme a decisão A acima.
Seu ponto de aplicação é aprovação/merge; o texto
não instala, remove, contorna nem modifica controles técnicos, tokens, permissões ou bots.
A comunicação pós-merge segue a autorização explícita acima; sem ela, preparar a mensagem
e registrar o gate, sem enviá-la. Diante de autoria ou contas do operador não comprovadas,
obter essa evidência antes de decidir. Limites de capacidade e gates vigentes permanecem
pré-condições, não punições automáticas por incidente.

## Quando usar / não usar

- **Usar**: o agente é raiz ou coordenador de trabalho em mais de uma sessão, harness ou
  subagente, e vai delegar, revisar, fazer commit ou reportar progresso.
- **Não usar**: tarefa de uma sessão sem delegação; operar sessões vivas (→ `omp-conductor`,
  se instalado); configurar MCP/skills de harness (→ `harness-concierge`); regras de
  profundidade e autoridade da delegação (→ `agentic-delegation`, a fonte única delas).
- **Limite**: esta skill é disciplina escrita. Ela não descobre, inicia, autentica nem integra
  harnesses; todo conector citado precisa estar montado no host que executa.

## Workflow (cada turno do coordenador)

1. **Medir estado**: ler uso de contexto e tamanho de `context_notes` se o host expuser; senão
   registrar `desconhecido` (Lei 2); obter o estado das sessões irmãs pelo relé somente-leitura
   (Lei 9). Pronto quando as duas métricas têm valor ou `desconhecido` e o digest do relé foi lido
   ou o erro dele registrado.
2. **Escolher o farol** pela tabela da Lei 1 e escrevê-lo na primeira linha da saída. Pronto
   quando a saída começa com exatamente um farol.
3. **Planejar o despacho**: para cada fatia, conferir na matriz (Lei 3) se o harness alvo tem o
   conector e priorizar multiplicadores verificáveis (Lei 4); aplicar assentos e admissão da
   Lei 13 e autoadoção limitada da Lei 17. Pronto quando cada fatia tem conector comprovado ou bloqueio e a fila respeita o teto.
4. **Despachar só o delta** com paths + SHA-256 (Lei 7) e autoridade igual ou menor (Lei 8).
   Pronto quando o brief não recopia contexto e declara seus limites.
5. **Revisar e registrar**: aprovação só por revisor distinto, presa ao SHA-256 dos bytes
   revisados (Lei 5); commit com `git add -- <arquivos>` (Lei 6). Pronto quando o hash
   revisado é igual ao hash entregue.
6. **Reportar**: antes de encerrar bloqueado, esgotar rotas autorizadas e entregar o kit da
   Lei 14 quando houver ação definida; manter o bloqueio real e a coownership E2E (Lei 10).
   Publicar Prep/CI, Prod Estrita e UVD binário separados (Leis 5 e 11), com StorageLocator
   e metadados da Lei 12. Rotacionar somente por limite observado da Lei 2; métrica desconhecida
   exige checkpoint 🟡 antes de despacho grande. Pronto quando há farol, evidência e próximo passo.

## Entrega gerenciada (instalação não prova ativação)

1. Conferir a fonte e seu StorageLocator externo. Termina com `source_sha256`, origem e
   modo observados; declaração de versão não prova instalação nem ativação.
2. Antes de qualquer mutação OMP, pré-renderizar o derivado pelo serializador nativo
   observado. `manage_skill` recebe `name`, `description` e `body` sem frontmatter; gera
   YAML somente com `name`/`description` sanitizados, uma linha em branco, `body.trim()`
   e newline final. `version`/`supersedes` permanecem no frontmatter da fonte e
   explicitamente no corpo de ambos, não como campos inventados da API. Termina com
   fonte e derivado congelados, `source_sha256` e `managed_sha256_expected` separados,
   contrato/versão do serializador registrados e limite nativo de bytes respeitado.
3. Obter revisão independente da fonte E do derivado exatos (Lei 5). Termina com
   veredito PASS por modelo distinto do autor, provider/modelo identificados e preso
   aos dois SHA-256; outra instância do mesmo modelo ou fixture não cumpre esse gate.
   PASS técnico não amplia a autorização existente nem dispensa gates operacionais.
4. Após PASS dos bytes finais e confirmação da rota e autorização aplicáveis,
   instalar no OMP por `manage_skill`, `action="update"`, destino managed `panoptes`,
   `description` da fonte revisada e `body` Markdown sem frontmatter. Conferir novamente
   contrato disponível, ownership, backup e pins; preservar links existentes, sem
   escrita direta em skills autorais/managed nem symlink de contorno. Sem ferramenta
   nativa, manter `INSTALL_BLOCKED`, sem inventar CLI equivalente. Em outro harness,
   usar apenas sua rota autorizada, com ownership e revisão comprovados. Termina com
   receipt e SHA instalado igual a `managed_sha256_expected`, não a `source_sha256`.
   Refresh pode falhar depois da escrita: medir antes de repetir, nunca presumir rollback.
   Carregamento pelo harness e ativação comportamental exigem evidências separadas.

Sem capacidade de revisão por modelo distinto: entregar fonte + derivado + hashes e
manter `REVIEW_PENDING`, sem instalar/promover. A decisão A está resolvida; não recriar
um gate A/B nem dispensar os restantes. A próxima ação é revisar os hashes finais em
capacidade autorizada, sem duplicar worker; sem rota nativa, manter `INSTALL_BLOCKED`.

## As 17 Leis Invariantes (1–17)

**Procedência v3.6.0:** 1–9 e 13–14 são preservadas da fonte managed v3.5.0.
O operador forneceu 10–12 nesta solicitação PRM138 v8.0.0. A definição histórica dos seis
metadados, ORPH01–10 e ADRs 051–055 não foi recuperada nas fontes consultadas.
As definições operacionais da Lei 12 são **especificação local desta solicitação**,
não doutrina histórica comprovada nem conteúdo atribuído a esses ADRs. Não inferir versão 3.4.0.
A Lei 15 vem da interjeição PRM139 v8.1.0; não recebe atribuição retroativa a ADR.


**Procedência v4.0.0 (PRM148 v8.5.0):** base v3.9.0 do barramento PRM145,
SHA-256 `4b9ef98cb0451658a2ce811c0724bee8390ef4a037a2430c9118960c61c93960`, derivada da fonte
managed v3.6.0, SHA-256 `0b5d5bf98d1c20eab2535cfe1af4418efe99c8622ba87d662c7144330dfb21bd`.
As Leis 1–15 permanecem com os bytes da v3.9.0. A Lei 16 e o juiz ADR-056 são instruções expressas
do operador (PRM141 v8.2.0, PRM145 v8.4.0, reafirmadas em PRM148 v8.5.0); os rótulos
ADR-056/057/058 são **referências pedidas pelo operador, não texto histórico desses ADRs**, cujo
texto canônico, e o da regra t250u, não foi recuperado. Não inventar versões 3.7/3.8, semântica
de t250u nem ratificação histórica. ADR-058 entra como **desenho** (seção após a Lei 16), nunca como
runtime comprovado. O handoff histórico M1/M2 fica no registro externo autorizado da entrega,
SHA-256 `3a83a2b51b80360518d33501e00b774f05e2b34e9d592692d2c43d4bdd2a38e2`;
o locator privado não faz parte da distribuição pública.
Estado de revisão/instalação: consultar o receipt externo da entrega e seus hashes; instalação
somente por `manage_skill`. Nenhum status desta documentação substitui a revisão dos bytes atuais.

**Procedência v4.2.0 (PRM155 v8.7.0):** preserva os núcleos das Leis 1–16 e o
juiz ADR-056/ADR-057 da baseline managed v4.0.1, SHA-256
`676c84daf1f8e21bef9a6c596101d30fee4dd34d6ed8fa7efd93ff40224503b4`.
A Lei 17 e o rótulo ADR-059 são a diretiva local do operador nesta solicitação, não
reconstrução de ADR cujo texto histórico não foi recuperado. ADR-058 permanece desenho
invariante com apontador para evidência externa; esta documentação não afirma implantação,
liveness, uso, CSAT nem capacidade efetivamente disponível de cinco harnesses.

**Procedência v4.3.0 (PRM155 v8.8.0):** parte da baseline managed v4.2.0,
SHA-256 `269f41a7f2908034753a0aed5c10900ef368ddd041da04e3fa9bde614adde7e8`.
Preserva os núcleos das 17 leis e os seis passos da Lei 17; atualiza somente a terminologia
atual de capacidade para **5 Slots × 3 Workers = 15 Threads**, no máximo 3 Workers por Slot,
e mantém os limites menores da raiz, host, profundidade, headroom global e churn. Slot não
é harness instalado nem prova de capacidade disponível. ADR-056/057 permanecem regras de
decisão/completude, ADR-058 permanece desenho e ADR-059 especificação local, sem ratificação
histórica, implantação, liveness, uso ou CSAT presumidos.

### Lei 1 — Farol Semiótico no topo

- **Regra:** toda saída para o operador começa, na primeira linha, com exatamente um farol
  cujo significado é verdadeiro no momento da emissão. Se mais de um se aplica, use o primeiro
  na ordem 🔵 > 🔴 > 🟣 > 🟡 > 🟢: um modal sem resposta bloqueia a sessão, e nada deve parecer
  pronto antes da aprovação do revisor.

  | Farol | Significado | Emitir quando |
  |---|---|---|
  | 🔵 | Responder modal/conflito | há decisão, modal ou conflito que só o operador resolve |
  | 🔴 | Nova sessão limpa ([+ New]) | um limite observado da Lei 2 foi atingido (contexto ≥ 60% ou `context_notes` ≥ 14 KB); citar no texto o path + SHA-256 do handoff |
  | 🟣 | Revisão independente em curso | a entrega está pinada por SHA-256 e aguarda revisor distinto (Lei 5); nada é declarado pronto antes da aprovação desse hash |
  | 🟡 | Cold-start ready | handoff gravado; qualquer sessão fria retoma a partir dele |
  | 🟢 | Follow-up | o próximo passo segue nesta sessão, sem decisão pendente do operador |

  O significado de 🟣 é definido por esta skill (v3.0.0), sem ADR nem fonte externa.
- **Gatilho:** início de cada turno, relatório ou handoff.
- **Anti-padrão:** saída sem farol ou com farol só no fim; dois faróis; 🟢 com decisão pendente
  do operador; 🟣 sem hash pinado ou sem revisor designado.

### Lei 2 — Gate anti-entropia

- **Regra:** manter contexto < 60% e `context_notes` < 14 KB. Rotacionar (farol 🔴, com path +
  SHA-256 do handoff no texto) somente quando um limite observado for atingido: contexto ≥ 60%
  ou `context_notes` ≥ 14 KB. Antes de um despacho que atingiria um limite, gravar handoff e
  reduzir ou adiar o despacho. Métrica que o host não expõe é `desconhecida`, nunca "abaixo do
  limite": com métrica desconhecida, gravar checkpoint/handoff conservador 🟡 antes de cada
  despacho grande, sem rotação compulsória; aplicar a precedência da Lei 1 se outro farol incidir.
  Cota de workers esgotada, ou insuficiente para o próximo despacho, também é limite observado:
  gravar handoff 🟡 e rotacionar ou devolver à raiz, nunca ampliar workers por conta própria (Lei 8).
- **Gatilho:** limite observado atingido (inclusive cota de workers); despacho que atingiria um limite; ou métrica desconhecida
  (checkpoint/handoff 🟡, não rotação compulsória).
- **Anti-padrão:** continuar até a compactação forçada; rotacionar sem handoff; zerar
  `context_notes` em vez de rotacionar; tratar ausência de métrica como folga.

### Lei 3 — Matriz estrita de conectores e zero IDs pré-alocados

- **Regra:** antes de delegar leitura ou escrita em sistema externo (Jira, GitHub, AWS, e-mail
  etc.), conferir na matriz que o harness alvo tem o conector montado. IDs externos (chave de
  ticket, número de PR/issue, ID de recurso) só são citados depois de retornados pelo host/API.

  | Harness | Conector | Evidência (comando/tool que provou) | Verificado em |
  |---|---|---|---|
  | `<harness>` | `<conector>` | `<saída observada>` | `<timestamp UTC>` |

  Célula sem evidência vale `desconhecido`, e `desconhecido` conta como "sem conector".
- **Gatilho:** delegação que toca sistema externo; plano que cita ticket ou PR futuro.
- **Anti-padrão:** pedir a um harness sem conector que "verifique o Jira"; pré-alocar
  `ABC-NNNN` ou `#NNN` antes de criar/ler o recurso.

### Lei 4 — Auto-multiplicadores primeiro

- **Regra:** priorizar trabalho que multiplica os próprios agentes (autonomia, observabilidade,
  IAM, CI/CD, mensageria entre agentes) antes de feature de custo equivalente, desde que
  dependência e ganho sejam verificáveis: nomear a tarefa repetida que ele elimina e a
  evidência (comando, log, contagem).
- **Gatilho:** priorização de backlog ou escolha entre frentes concorrentes.
- **Anti-padrão:** repetir à mão o que um multiplicador eliminaria; adiar IAM/CI quebrados para
  entregar feature; chamar algo de multiplicador sem dependência comprovada.

### Lei 5 — Executor ≠ Reviewer por SHA-256 e placar duplo

- **Regra:** quem produz não aprova. O revisor registra o SHA-256 dos bytes que revisou; se
  qualquer byte mudar depois, a aprovação está invalidada e a revisão recomeça. Evidência aceita:
  SHA-256 dos bytes, CI Run ID, S3 VersionId, ou comando + exit code junto com artefato não vazio
  ou seu hash. Exit code sozinho, rc=0 com saída vazia, artefato ausente, nome de arquivo ou
  resumo de chat não bastam. Reportar sempre dois números separados: **Prep/CI** (pronto, verde,
  revisado) e **Prod Estrita** (aplicado e verificado no ambiente real). Número não medido é
  reportado como `desconhecido`; nenhuma porcentagem estimada.
- **Gatilho:** qualquer afirmação de "pronto", "feito", "verde" ou percentual de progresso.
- **Anti-padrão:** auto-revisão; aprovação sem hash; "CI verde = produção"; percentual estimado
  apresentado como medido; evidência por resumo de chat.

### Lei 6 — Staging exato no Git

- **Regra:** preparar commit só com paths explícitos — `git add -- <arquivo1> <arquivo2>` — e
  conferir `git diff --cached --name-only` antes de `git commit`.
- **Gatilho:** qualquer commit, principalmente em worktree compartilhada.
- **Anti-padrão:** `git add .`, `git add -A`, `git add openspec/` ou qualquer diretório amplo;
  commit sem conferir a lista staged.

### Lei 7 — Compressão latente de deltas

- **Regra:** delegações e handoffs carregam só o delta e apontam artefatos pinados por path +
  SHA-256. Comprimir o texto, nunca a evidência: hashes, exit codes, paths, bloqueios e o caminho
  de recuperação ficam literais. Não alegar capacidade que o host não demonstrou.
- **Gatilho:** qualquer despacho, handoff ou relatório longo.
- **Anti-padrão:** colar o handoff completo no prompt; referenciar arquivo sem hash, que pode
  mudar entre despacho e leitura; resumo que perde rc ou hash; prometer ferramenta inexistente.

### Lei 8 — Propagação recursiva seletiva

- **Regra:** ao delegar, propagar só as leis e o contexto de que a fatia precisa, com autoridade
  igual ou menor que a sua e dentro dos limites atuais (profundidade, workers, prazo, orçamento).
  Ler uma skill, inclusive esta, não concede permissão. Nenhum agente amplia recursos ou escopo
  por conta própria; ampliação é pedido à raiz ou ao operador.
- **Gatilho:** qualquer delegação ou sub-delegação.
- **Anti-padrão:** copiar o contexto inteiro ao filho; filho com mais permissão que o pai; spawn
  além do limite; "auto-expandir" workers.

### Lei 9 — Barramento de entrada única, sem copy-paste

- **Regra:** o operador entrega cada rodada uma única vez, na sessão raiz. A raiz lê o estado das
  sessões irmãs por um relé somente-leitura (por exemplo `omp-relay`, que grava
  `LIVE-SESSIONS-DIGEST.json` com proveniência, timestamps, staleness e erros classificados) e
  devolve ao operador um único relatório pinado por hash. O relé só observa: nunca envia, injeta,
  retoma nem agenda loop em outra sessão, e o digest não leva prompts, transcrições, segredos nem PII.
- **Espera não disruptiva:** enquanto um dono ou revisor trabalha, não interromper nem fazer
  polling; aguardar a entrega com prazo declarado e seguir com trabalho independente. Prazo
  estourado vira pedido de extensão à raiz ou bloqueio registrado.
- **Fallback de autenticação no pré-voo:** se a autenticação de um conector falhar (token
  expirado, SSO, cofre de chaves travado), registrar comando, exit e erro classificado e escalar
  com 🔵; nunca extrair credenciais, contornar assinatura nem trocar de identidade sem autorização.
- **Gatilho:** início de rodada do operador; necessidade de estado de outra sessão; espera por dono
  ou revisor; falha de autenticação no pré-voo.
- **Anti-padrão:** pedir ao operador que copie e cole entre sessões; injetar prompt ou retomar
  sessão alheia; polling ou loop em background; digest com transcrição ou e-mail; commit sem
  assinatura ou credencial alternativa sem autorização.

### Lei 10 — Coownership E2E até PRD

- **Regra:** executor e raiz compartilham responsabilidade pelo resultado da frente até o efeito
  autorizado estar ativo e verificado em PRD ou, para comunicação, na caixa do destinatário.
  Commit, PR, CI, kit, artefato local e `local_done` encerram somente preparação; não encerram
  a frente. Registrar destino real, dono da próxima ação, gate e evidência faltante, para que
  nenhum handoff seja confundido com entrega externa.
- **Continuidade limitada:** executar agora as etapas técnicas já autorizadas dentro do escopo,
  prazo e caps vigentes. Ao atingir gate ou prazo, entregar checkpoint pinado e bloqueio à raiz,
  mantendo a frente aberta; transferência só se completa com aceite explícito do novo dono.
  Isso não exige processo eterno, polling, novos workers nem alteração de sessão com dono ativo.
- **ZeroHITL:** significa não pedir aprovação redundante para trabalho técnico já autorizado.
  Segurança, segredos, acesso/permissões, login/OAuth, produção, custos, envio, protected merge
  e DBA/DDL continuam não delegáveis e exigem o gate humano aplicável. Sem aprovação, preparar
  evidência e próximo comando, não executar a mutação. PII real mantém autorização explícita.
  A Regra 28 dispensa pergunta redundante somente dentro da autorização existente; não dispensa
  nenhum desses gates nem os controles reais do destino e não cria bloqueio geral por incidente.
- **Gatilho:** conclusão local, handoff, bloqueio, limite de prazo ou proposta de fechar uma frente.
- **Anti-padrão:** fechar por `local_done`, repassar sem aceite ou usar ZeroHITL para atravessar
  gate humano. Manter dono, bloqueio e próximo passo explícitos até o efeito comprovado.

### Lei 11 — UVD binário separado de WIP

- **Regra:** por entrega e destino definidos, registrar `UVD=0` até haver evidência do efeito
  ativo e verificado em PRD; para comunicação, evidência de chegada à caixa do destinatário.
  Só então `UVD=1`. Fonte ausente, efeito desconhecido, draft, clipboard, aceite de API,
  MessageId isolado, deploy iniciado, merge ou CI verde mantêm `UVD=0`.
- **Medição:** manter WIP/Prep/CI e Prod Estrita em campos separados. Para N entregas com
  identidade e destino enumerados, `UVD%=100*sum(UVD)/N`; denominador desconhecido ou N=0
  é `não medido`, não 100%. Evidência inclui UTC, destino, identificador real e locator pinado,
  com dados privados minimizados. Não generalizar a prova de um destinatário aos demais.
- **Gatilho:** placar, percentual, fechamento ou alegação de valor entregue.
- **Anti-padrão:** UVD parcial por preparação, entrega presumida por envio ou soma de WIP em UVD.
  Reportar o binário por entrega e explicitar o critério externo ainda não satisfeito.

### Lei 12 — StorageLocator e seis metadados anti-órfãos

- **Regra:** cada artefato entregue tem um `StorageLocator` com `Path` absoluto do arquivo,
  `URI` resolvível pelo consumidor, `Fallback` durável independente do temporário/sessão de
  origem e `SHA256` dos bytes finais. Testar leitura autorizada de Path, URI e Fallback e
  comparar os três hashes; sem acesso, registrar bloqueio em vez de afirmar recuperação.
  Não copiar segredos, publicar nem conceder acesso para satisfazer o locator.
- **Seis metadados locais:** usar os campos abaixo junto ao locator; são a especificação local
  PRM138, não uma reconstrução de ADRs. Campos compostos continuam um metadado lógico.

  | Campo | Conteúdo verificável e finalidade |
  |---|---|
  | `artifact_id` | Identidade única e estável da entrega; impede colisão entre frentes. |
  | `owner` | Papel responsável e rota de contato existente; permite cobrar a próxima ação. |
  | `origin` | Solicitação/frente, fonte pinada e relação com a entrega; preserva procedência. |
  | `lifecycle` | Estado real, destino e retenção/condição de descarte; separa WIP de entregue. |
  | `timestamps` | `created_utc` e `updated_utc` ISO-8601; permitem detectar evidência obsoleta. |
  | `next_action` | Ação executável, dono, gate e prazo/trigger; na entrega final, ação de aceite/consulta. |

- **Verificação local ORPH01–10:** executar uma vez antes do handoff e após mudança dos bytes
  ou dos locators; falha deixa o artefato `RECOVERY_BLOCKED`, preserva os bytes e volta ao dono.

  | Gate local | Passa quando |
  |---|---|
  | ORPH01 | `artifact_id` não vazio e sem colisão no manifesto da frente. |
  | ORPH02 | `owner` tem papel e rota de contato comprovada, sem inventar pessoa/ID. |
  | ORPH03 | `origin` liga solicitação, frente e fonte com hash ou identificador imutável. |
  | ORPH04 | `lifecycle` declara estado, destino e retenção/condição de descarte. |
  | ORPH05 | Datas UTC são válidas, criação ≤ atualização, e revisão usa o hash atual. |
  | ORPH06 | `next_action` nomeia ação, dono, gate e prazo/trigger sem aprovação presumida. |
  | ORPH07 | `Path` é absoluto, arquivo não vazio e legível pelo consumidor autorizado. |
  | ORPH08 | `URI` resolve os mesmos bytes por rota existente e autorizada. |
  | ORPH09 | `Fallback` permanece recuperável fora do temporário/sessão de origem. |
  | ORPH10 | SHA-256 dos três locais coincide com o pin final; alteração invalida aprovação. |

- **Publicação:** registrar os locators em manifesto separado dos artefatos; não inserir o hash
  do próprio relatório dentro dele. Para artefato sensível sem cópia autorizada, manter
  `RECOVERY_BLOCKED` com gate de armazenamento, não contornar acesso nem prometer fallback.
- **Gatilho:** criação de entrega, mudança de bytes/localização ou handoff de cold-start.
- **Anti-padrão:** path `/tmp` isolado, URI não testada, hash autorreferente ou seis campos sem
  dono/recuperação. Entregar manifesto verificável ou bloqueio explícito com próximo passo.

### Lei 13 — Named Persistent Seats & Queue Discipline

- **Regra:** `conductor-lead`, `spec-builder`, `cross-model-reviewer`, `last-mile-cutover` e
  `pmo-quick-sync` são papéis funcionais persistentes no plano, não cinco processos ativos nem
  IDs de harness. Um executor pode cobrir vários papéis, mas nunca revisar os próprios bytes
  (Lei 5). Registrar dono e estado observados para separar função de capacidade real.
- **Admissão:** assentos não ampliam profundidade máxima da raiz 3, filhos diretos da raiz 3,
  teto global da sessão 15 ou churn 30. Aplicar sempre o menor limite vigente do host e da
  autorização; LEAF com `depth_remaining=0` não cria nem retoma filhos. Com subagentes
  executando no quadrante, aceitar `queued=0` ou `queued=1`; bloquear `queued>=2` e devolver
  nova admissão à raiz. Registrar contagens desconhecidas como desconhecidas, sem presumir folga.
- **Redirect:** redirecionar somente após comprovar no quadrante de destino liveness `idle`,
  conector necessário e autorização para a ação. `idle` desconhecido falha fechado: manter
  fila no máximo 1 e devolver admissão à raiz; sem peer injection, copy-paste ou autostarts.
- **Gatilho:** planejar assentos, admitir trabalho ou considerar redirect enquanto há executores.
- **Anti-padrão:** cinco nomes virarem cinco workers; inventar IDs; fila 2+ com filhos ativos;
  usar silêncio como prova de idle. Manter papéis lógicos e evidência de capacidade real.

### Lei 14 — Last-Mile UVD Closer & One-Click Cutover Kit

- **Regra:** antes de encerrar `DISPATCH_BLOCKED` ou `BLOQUEADO-DBA`, enumerar e tentar somente
  rotas CLI/API existentes, autorizadas e pertinentes ao escopo. Registrar UTC, rota, evidência
  de autorização, comando sanitizado, exit code e resultado. Ausência de rota autorizada é
  prova legítima de esgotamento; não exige operação ilegal, force-auth ou fallback de segredos.
  Um inventário comprovado sem permissão termina em bloqueio, não em tentativa de mutação.
- **Kit:** para ação de cutover definida, entregar `one-click-cutover.sh` implementado, com
  inputs e pins explícitos, escopo de ação, `--check` sem mutação, preflight fail-closed,
  idempotência e postcheck que prove o efeito. A execução para antes de cada gate ausente;
  `bash -n` sozinho não prova operação. Quando faltarem inputs ou autorização, registrá-los
  como pré-condição bloqueada; não substituir implementação por stub ou sucesso fictício.
- **HITL:** DBA/DDL, envio, login/OAuth, permissões, segredos, custos e mutações cloud preservam
  seus gates humanos. Kit gerado ou `--check` aprovado não autoriza execução, não prova envio,
  apply ou produção e não converte UVD em 100%. Manter o bloqueio real no relatório após o kit.
- **Limite:** inventariar cada rota pertinente uma vez por rodada; nenhuma repetição autônoma
  após falha ou expansão de autorização. Mudança de credencial/escopo volta à raiz ou operador.
- **Gatilho:** fechamento bloqueado ou preparação de cutover autorizado.
- **Anti-padrão:** arquivo existente contado como efeito externo; forçar login para remover
  bloqueio; esconder DBA atrás de one-click. Separar preparação, execução e verificação real.

### Lei 15 — Opção ótima ativa com todos os gates

- **Regra:** diante de conflito entre entrega e restrições, sintetizar a melhor rota alternativa
  que satisfaça **todos** os gates vigentes ao mesmo tempo. Comparar rotas reais por segurança,
  correção, reversibilidade, idempotência e efeito verificável; escolher a de menor risco que
  atenda o objetivo autorizado. Não remover um gate para melhorar a pontuação de outro.
- **Execução limitada:** uma avaliação por conflito e uma tentativa por rota autorizada na
  rodada, dentro do prazo e caps recebidos. Usar alternativa transacional/idempotente quando
  aplicável; verificar suas pré-condições antes da ação. Capacidade, autenticação, aprovação
  e atomicidade não demonstradas permanecem desconhecidas, não viram promessa.
- **Bloqueio irredutível:** registrar as rotas consideradas, evidência de inviabilidade, a
  melhor opção restante, gate humano/pré-requisito exato, dono e próximo comando condicional.
  Entregar o kit completo sem executar a ação vedada; manter UVD=0 e a frente aberta.
  Isso satisfaz a disciplina de resolução, não prova o resultado externo.
- **Gatilho:** conflito de requisitos, falha de rota ou alegação de bloqueio sem alternativa avaliada.
- **Anti-padrão:** escolha binária entre burlar gate e desistir; inventar capability, tentar
  indefinidamente ou declarar produção pelo kit. Sintetizar alternativa segura e explicitar o limite.


#### Juiz e gerador de opção ótima — ADR-056 (NEW_SPEC_PRM145)

1. **Julgar o conflito**: enumerar objetivo, autoridade, dono, prazo/caps e cada gate aplicável;
   registrar fonte pinada e predicado observável. Termina com uma matriz sem gates implícitos.
2. **Gerar e comparar rotas reais**: incluir a rota direta, uma alternativa segura e o bloqueio
   honesto. Filtrar primeiro por todos os gates; dentre as viáveis ordenar por segurança,
   correção, reversibilidade, idempotência e efeito verificável, com razões verificáveis.
   Termina com a melhor rota **entre as avaliadas**, não uma promessa de ótimo global.
3. **Executar ou preparar**: uma tentativa por rota autorizada na rodada, sem novos workers
   além dos caps. Nas três classes recorrentes, usar o resolver: `sql-atomic-wrap` transforma
   bytes e nunca aplica DB; `child-status` só observa fonte nativa e falha fechado quando
   desconhecida; `verify-delivery` testa bytes/locators/proveniência ou efeito explícito.
   Termina com comando sanitizado, UTC, exit e hash de saída não vazia, ou pré-requisito exato.
4. **Aceitar sem autoaprovação**: Lei 5 governa o aceite e a Lei 16 governa completude.
   Mudança de bytes invalida revisão. Termina com Prep/CI, Prod Estrita, UVD e CSAT separados.

O mecanismo não executa DB/DDL, merge, deploy, envio, login, mudança de permissão nem
resgate de peer. Capacidade ausente ou revisão indisponível mantém o bloqueio e entrega
kit/artefatos completos. A exceção legítima é não haver rota autorizada; a evidência dessa
ausência satisfaz a disciplina, não entrega externa. Reavaliar esta extensão somente por
mudança de fonte/autoridade ou pelos critérios DUED desta skill.

### Lei 16 — Completude 100% = UVD em produção e usuário feliz

- **Regra (ADR-057, NEW_SPEC_PRM145):** para cada entrega e destino enumerados, 100% exige
  simultaneamente efeito autorizado ativo e verificado no ambiente real de produção (UVD),
  evidência de uso real e satisfação confirmada, atribuível ao usuário/stakeholder humano ou
  agente consumidor (CSAT). Preparação, merge, API aceita, self-test e inferência de sentimento
  não satisfazem esse conjunto. A confirmação de CSAT identifica fonte, alvo, UTC e locator
  pinado; não fabricar confirmação, destinatário ou legitimidade da fonte.
- **Medição:** registrar separadamente `UVD∈{0,1}`, `uso_real∈{0,1,desconhecido}` e
  `CSAT∈{0,1,desconhecido}`. `completo=1` somente se UVD=1, uso_real=1 e CSAT=1 para
  **todos** os destinos. Denominador ausente ou zero significa `não medido`; desconhecido
  nunca vira 100%. Evidência local de integridade não autentica, sozinha, o observador externo.
  Na comunicação, a chegada à caixa do destinatário segue Lei 11; clipboard/draft não basta.
- **Continuidade limitada:** terminar todo trabalho técnico alcançável autorizado nesta rodada;
  ao gate irredutível ou prazo/cap recebido, preservar evidência e devolver à raiz com dono,
  pré-requisito exato e próximo comando condicional. Manter a frente aberta; não criar loop
  eterno nem pedir confirmação redundante para técnica já autorizada. Satisfação pendente
  não autoriza pressionar o usuário, enviar mensagens ou atravessar qualquer HUMAN_DOMAIN.
- **Gatilho:** percentual de completude, pedido de fechamento ou afirmação de usuário feliz.
- **Anti-padrão:** equiparar WIP a valor; self-test como UVD; fonte ausente como CSAT; presumir
  felicidade pelo silêncio. Emitir placar separado e o critério externo não satisfeito.

#### Desenho ADR-058 — OpenRig ACP Seats + Buzz/OMP-Relay + Nod-n8n (arquitetura)

Rótulo pedido pelo operador; texto canônico de ADR-058 não recuperado. Esta seção define
responsabilidades e fronteiras invariantes, não o estado operacional de uma instalação.

| Componente | Papel arquitetural | Fronteira invariante | Interface de evidência externa |
|---|---|---|---|
| OpenRig ACP Seats | Mapear os assentos funcionais da Lei 13 a seats ACP | Seats não ampliam caps, autoridade ou ownership; operação segue o playbook aplicável | Relatório operacional da rodada com fonte nativa, alvo, UTC, comando autorizado, exit e hash |
| Buzz / OMP-Relay | Observação read-only e aviso pelo barramento da Lei 9 | O relé observa sem injetar, retomar ou agendar sessões; aviso não concede autoridade | Digest e recibo de entrega pinados no manifesto externo, com proveniência e staleness explícitas |
| Nod-n8n | Executar fluxos autorizados da frente | Isolamento, menor privilégio e gates HUMAN_DOMAIN precedem cada ação; efeito, uso e CSAT seguem Leis 11 e 16 | Relatório externo de alvo, autorização, isolamento e efeito ponta a ponta; integridade local não substitui observação externa |

O manifesto operacional separado segue o StorageLocator e os seis metadados da Lei 12.
A interface exige fontes pinadas, observações datadas e revisão distinta (Lei 5); valores de
liveness, smokes, versões instaladas e origens de credenciais ficam somente nesses artefatos,
fora da doutrina. Locators privados de recuperação pertencem ao registro externo autorizado
da respectiva rodada, nunca à distribuição pública nem à prova atual. Ao citar ADR-058,
o relatório da rodada distingue desenho de observação e explicita evidência faltante.

#### Child-Harness Rescue & Push-to-100% (limites das Leis 8, 9 e 13)

1. **Observar antes de agir:** capturar fonte nativa read-only com linhagem, liveness e UTC.
   Receipt/transcript antigo, processo de nome parecido ou ausência na lista não prova idle.
   Termina com estado positivo comprovado ou `UNKNOWN`, nunca sucesso por silêncio.
2. **Conferir admissão e ownership:** dono, conector, autorização original, profundidade,
   headroom/churn, fila e prazo são pré-condições cumulativas. Termina com rota permitida
   documentada ou bloqueio à raiz; caps não se reiniciam com contagem de finished.
3. **Resgatar somente pela rota já autorizada:** uma tentativa por rota na rodada; respeitar
   dono ativo e espera não disruptiva. Falta de reviver nativo encerra essa rota, sem duplicar
   reviewer, peer injection, CLI assistant ou processo background para contornar o cap.
   Termina com resultado nativo e artefato terminal, ou erro classificado pinado.
4. **Fechar pela Lei 16:** coletar efeito, uso e CSAT reais quando autorizados; caso contrário
   checkpoint completo com StorageLocator. Termina com aceite do novo dono explícito ou
   bloqueio mantido; kit não é implantação, e doutrina não concede permissão de produção.

### Lei 17 — Autoadoção proativa limitada e teto por Slots (ADR-059)

- **Regra (NEW_SPEC_PRM155):** adotar proativamente itens de backlog somente quando forem
  dependências ou melhorias diretamente necessárias ao objetivo já autorizado pelo operador.
  A autoadoção reutiliza a autorização existente; não cria nova autorização, permissão de
  produção nem dispensa HUMAN_DOMAIN, revisão independente ou DBA/DDL. Backlog sem vínculo
  demonstrado fica fora da execução e volta à raiz como proposta, sem iniciar outra frente.
- **Teto, não capacidade instalada:** no máximo **5 Slots × 3 Workers = 15 Threads**;
  por Slot (incluindo S1), no máximo **3 Workers ativos**, contando coordenador e filhos no
  mesmo limite. Aplicar o menor entre esse teto e os limites vigentes da raiz, host,
  profundidade, headroom global e churn (Leis 2, 8 e 13). Slots e assentos lógicos não são
  processos comprovados nem reserva de capacidade; Slot é uma unidade de admissão, não um
  harness adicional. Liveness ou contagem desconhecida falha fechado para nova admissão;
  manter checkpoint e devolver à raiz. Trocar nomes, sessões, Slots ou harnesses não reinicia
  caps nem autoriza autostart recursivo.
- **Operação verificável, uma passagem por item na rodada:**
  1. **N-Tree + RACI/DARCI:** ligar o item ao objetivo e à cadeia de dependências existente;
     registrar um único dono de execução e um único aprovador com autoridade comprovada,
     distinguindo ambos para os mesmos bytes (Lei 5). Consultados e informados não recebem
     autorização implícita; sem dono/aprovador válido, preparar o bloqueio para a raiz.
  2. **GUT + Eisenhower:** ordenar os itens elegíveis por gravidade, urgência e tendência,
     justificadas por evidência, e por urgência/importância; dependências e gates precedem
     pontuação. Registrar a próxima ação priorizada, sem inventar números não medidos.
  3. **5 Why + Ishikawa:** para falha ou impedimento observado, rastrear causas com evidência
     e separar hipótese de causa confirmada; usar até cinco porquês e agrupar causas no
     diagrama de Ishikawa quando houver ramos. Encerrar ao limite da evidência, sem simular
     cinco respostas nem transformar diagnóstico em ampliação do escopo.
  4. **5W2H:** definir o que, por quê, onde, quando, quem, como e custo/recursos autorizados
     da ação escolhida. Campo desconhecido permanece explícito; pré-condição de execução
     ausente bloqueia a ação, e custo não autorizado escala ao operador.
  5. **Blast Radius:** limitar alvos, arquivos/recursos, efeitos externos e reversibilidade
     antes de executar. Usar somente conectores comprovados e rotas autorizadas; registrar
     predicado de sucesso e condição de parada. Risco, permissão ou gate fora da autorização
     encerra a execução do item e devolve evidência à raiz, sem contornar o gate.
  6. **Boy Scout limitado:** limpar apenas resíduos diretamente tocados pela ação autorizada
     e necessários à correção/manutenibilidade, dentro do mesmo Blast Radius, prazo e caps.
     Preservar WIP alheio e exigir revisão dos bytes finais; melhoria adjacente não necessária
     vira proposta, não drenagem automática de backlog nem autostart fora do objetivo.
- **Evidência e término:** registrar item, vínculo ao objetivo, dono/aprovador, decisão,
  ação/efeito observado e bloqueio em artefato externo pinado (Lei 12). Encerrar a passagem
  ao resultado ou gate/prazo/cap recebido, sem loop autônomo nem reprocessamento sem mudança
  de pré-condição; completude continua regida pelas Leis 11 e 16.
- **Procedência:** ADR-059 é o rótulo solicitado pelo operador em **PRM155 v8.7.0**;
  este conteúdo é especificação local dessa diretiva, não texto histórico recuperado de ADR.
  A Lei 17 não altera os núcleos das Leis 1–16 nem o desenho ADR-058.
- **Gatilho:** item de backlog encontrado durante o objetivo autorizado; priorização ou
  admissão por Slots dentro da rodada.
- **Anti-padrão:** autoadoção de backlog alheio ao objetivo; usar teto como prova de implantação
  ou folga; dono que autoaprova; saltar produção/HITL; iniciar filhos recursivos ou drenar
  backlog sem autoridade. Em vez disso, executar só o item elegível nos limites comprovados
  ou devolver proposta/bloqueio pinado à raiz.

## Rotina complementar (herdada da v2.1.0)

- A cada 3 turnos, registrar telemetria: estado, placar duplo, bloqueios e farol.
- Toda sessão termina com handoff de cold-start que permite retomada sem a conversa, com paths
  pinados por hash.

## Reconciliação com a lista do operador (PRM-107/110/121)

A numeração 1–9 e 13–14 da 3.5.0 foi preservada. A 3.5.1 incorporou 10–12 do operador
PRM138 v8.0.0; a 3.6.0 acrescenta 15 do PRM139 v8.1.0, mantendo os gaps históricos rotulados.

| Item do operador | Onde está |
|---|---|
| Farol 🟢 Follow-up · 🔵 Modal/Conflito · 🔴 Nova sessão · 🟡 Cold-start | Lei 1 (🟣 é extensão da 3.0.0, fora da lista do operador) |
| Rotação anti-entropia: contexto 60%, `context_notes` 14 KB, cota de workers | Lei 2 |
| Matriz de conectores, zero IDs externos pré-alocados | Lei 3 |
| Auto-multiplicadores | Lei 4 |
| Owner ≠ Reviewer por SHA-256, placar duplo Prep/CI × Produção | Lei 5 |
| Despacho só de deltas pinados por hash | Lei 7 |
| Telemetria de 3 turnos + handoff de cold-start | Rotina complementar |
| Espera não disruptiva + fallback de autenticação no pré-voo | Lei 9 |
| Barramento de entrada única, sem copy-paste | Lei 9 |
| (sem item correspondente) | Leis 6 (staging exato) e 8 (propagação seletiva), mantidas da 3.0.0 |
| Coownership E2E sem fechar por local_done | Lei 10 (PRM138 v8.0.0) |
| UVD binário por entrega, separado de WIP | Lei 11 (PRM138 v8.0.0) |
| StorageLocator, seis metadados e ORPH01–10 | Lei 12 (especificação local PRM138 v8.0.0) |
| Assentos funcionais persistentes, fila 0/1 e redirect comprovado | Lei 13 (PRM-136; referência proposta, sem ADR atribuído) |
| Esgotamento autorizado, kit implementado e bloqueios reais preservados | Lei 14 (PRM-136; referência proposta, sem ADR atribuído) |
| Melhor rota alternativa satisfazendo todos os gates | Lei 15 (PRM139 v8.1.0; juiz ADR-056 como rótulo do operador) |
| Efeito em PRD + uso real + CSAT confirmado do usuário/cliente, sem equivaler WIP a completude | Lei 16 (ADR-057, rótulo do operador; texto histórico não recuperado) |
| OpenRig ACP Seats + Buzz/OMP-Relay + Nod-n8n | Desenho ADR-058 após a Lei 16; runtime não afirmado |
| Autoadoção proativa só no objetivo autorizado; teto 5 Slots × 3 Workers = 15 Threads e ≤3 Workers por Slot, menores caps prevalecem | Lei 17 (ADR-059, especificação local PRM155 v8.7.0; terminologia PRM155 v8.8.0) |

## Evidência mínima

```bash
shasum -a 256 <artefato>          # hash citado no despacho/relatório (Leis 5 e 7)
git add -- <arquivos exatos>      # Lei 6
git diff --cached --name-only     # conferir a lista antes do commit
```

## Exemplos

- **Comando exato ≠ diagnóstico controlado:** o operador pediu um comando de teste exato; com
  `NODE_ENV=production` herdado ele saiu com exit 1. O resultado real foi reportado como tal; a
  execução com `NODE_ENV=test` foi reportada à parte, como diagnóstico.
- **Explore mode não escreve código:** em refinamento, as decisões registradas nos docs de
  estudo foram lidas e tratadas como fechadas; nenhum arquivo de código foi alterado.
- **Falha de assinatura vira HITL:** `agent returned an error` no commit assinado gerou pedido de
  desbloqueio ao operador (🔵), sem `--no-gpg-sign`.
- **Gate de pré-condição pode parar sem escrever:** sem prova da pré-condição exigida, o gate
  encerrou o turno sem nenhuma escrita, e isso foi um resultado válido.

## Validação

1. Frontmatter em YAML estrito, sem chaves duplicadas; `name` igual ao diretório,
   `description` ≤1024 caracteres; fonte com versão candidata 5.2.0 e `supersedes: 5.1.0`,
   sem alegar baseline 5.1.0 recuperada. Derivado OMP: YAML nativo name/description,
   versão/supersedes no corpo; pins fonte/derivado separados, via entrega gerenciada.
2. Exatamente dezessete cabeçalhos `### Lei N` (N = 1..17), cada um com Regra, Gatilho e
   Anti-padrão; comparar a doutrina com a baseline 4.3.0 pinada, considerando a harmonização
   explícita da Lei 10/§0 com o Ring0 e a retirada de locators privados. Lei 12 distingue
   especificação local de história; Lei 17 atribui ADR-059 somente à diretiva local PRM155.
3. Smoke de leitura por executor isolado: no cenário em que o único harness disponível não tem
   conector comprovado para o sistema externo e o host não expõe uso de contexto, a saída
   esperada começa com 🔵, registra `desconhecido` na matriz e no placar, grava checkpoint antes
   do despacho e não cita ID externo que não tenha sido retornado.
4. Autovalidade (`rule-quality-tests`): Self-Application · Non-Contradiction · Survival ·
   Bounded-Responsibility · Explicit-Exception · Utility-Sunset — julgada por revisor
   independente em modelo distinto do autor, conforme entrega gerenciada e Lei 5.
5. Smoke de admissão com filhos ativos: `queued=0` e `1` passam; `2` bloqueia; redirect com
   `idle` desconhecido bloqueia mesmo com conector e autorização. Não criar workers no smoke.
6. Dogfood de uma rodada real: três fatias independentes, papéis lógicos sem cinco processos,
   revisão posterior por executor distinto. Registrar criados/retomados pelo leaf = 0;
   contagens globais não observadas continuam desconhecidas. Lei 14 não remove gate DBA.

7. Lei 17: item sem vínculo ao objetivo, permissão nova, liveness desconhecida ou menor cap
   esgotado bloqueia execução/admissão; item elegível tem dono/aprovador distintos e ação
   limitada por N-Tree, RACI/DARCI, GUT/Eisenhower, 5 Why/Ishikawa, 5W2H, Blast Radius e
   Boy Scout. Validar por revisão sem criar processos nem drenar backlog fora do escopo.

8. Ring0 contém uma única Regra 28, com o delta da decisão explícita A atribuído ao
   operador, sem fingir literalidade ao bloco anterior. Revisar os três sinais, autoria
   por login/contas verificadas e is_bot, ator do merge e autorização de mensagens;
   nenhuma validação altera bots, credenciais ou controles reais.
   Conferir que a distribuição pública não contém nomes, repositórios ou dados pessoais de
   outros mundos. A validação e o PASS pertencem ao revisor dos bytes finais, não ao autor.

## §DUED Sunset

Deprecar quando: o host oferecer gate nativo equivalente às 17 leis (E1); a família de delegação
absorver estas leis numa entrada única (E6); o operador retratar a skill (E4); ou houver ≥ 3
falsos positivos documentados (E5).

## Refs

- `skills/agentic-delegation` — profundidade e autoridade de delegação (fonte única da Lei 8).
- `agents/orchestrator.md` — a raiz delega e audita. · `skills/harness-concierge` — onde cada
  harness guarda configuração.
- `agents/forge.md` (Goldilocks · RBAD · 33 perguntas) · `skills/agentic-tool-forge` ·
  `skills/anima` · `bin/artifact-registry`.
- Cross-link: `[[panoptes]]`.

## Changelog

| Versão | Data | Mudança |
|---|---|---|
| 5.2.0 | 2026-11-23 | Candidato PRM298: declara `supersedes: 5.1.0` por diretiva do operador, sem inventar baseline/histórico 5.1.0; deriva da 4.3.0 pinada. Inclui RULE-COGNITION-OVER-CASTRATION-28 no Ring0, harmoniza §0/Lei 10 e remove locators privados. F1/F2: distingue fonte/derivado nativo e pins, restaura PASS por modelo distinto. Decisão posterior explícita A: avisar-e-seguir dentro da autorização, login verificado + não bot, autor do PR e ator do merge separados; não atribui refinamentos ao bloco anterior. Delta-review: restaura integralmente os gates herdados da Lei 10, incluindo Segurança/protected merge, sem aprovação redundante ou dispensa dos gates. Preserva as demais leis; revisão, instalação e ativação são estados externos separados. |
| 4.3.0 | 2026-11-19 | PRM155 v8.8.0: capacidade passa a 5 Slots × 3 Workers = 15 Threads e ≤3 Workers por Slot, coordenador incluído; menores caps continuam prevalecendo. Preserva os 17 núcleos, os seis passos ADR-059 e ADR-056/057; ADR-058 permanece desenho. Atualização gerenciada e revisão por hash não provam ativação nem capacidade instalada. |
| 4.2.0 | 2026-11-19 | PRM155 v8.7.0: acrescenta Lei 17/ADR-059 como diretiva local, autoadoção limitada ao objetivo autorizado e teto 5 harnesses × 3 workers = 15 threads, S1 ≤3 ativos e menores caps prevalecentes. Preserva núcleos 1–16, ADR-056/057 e ADR-058 design-only; não implanta harnesses nem remove gates. |
| 4.0.1 | 2026-11-19 | PRM152 v8.6.0: ADR-058 contém só arquitetura invariante e interface para evidência externa; remove células de estado efêmero. Preserva núcleos das 16 leis e semântica ADR-056/057; atualização gerenciada e alias pinado não constituem revisão independente nem ativação. |
| 4.0.0 | 2026-11-18 | PRM148 v8.5.0: preserva Leis 1–16 e referências ADR-056/057/058; desenho separado de integração implantada. Correções de revisão: estado por receipts externos, versão explícita no corpo e tabela histórica com STOP-HITL Nod, mapeamento Crew confirmado e gates não verificados; sem ativação ou autoaprovação. |
| 3.9.0 | 2026-11-18 | Candidato PRM145: preserva 1–14 e núcleo 15; juiz/gerador e Lei 16 com UVD + uso real + CSAT atribuível como NEW_SPEC_PRM145, não ADR histórico recuperado; resgate limitado, sem ativação ou autoaprovação. |
| 3.6.0 | 2026-11-18 | PRM139 v8.1.0: Lei 15 exige síntese ativa da melhor alternativa que satisfaça todos os gates, tentativa limitada e bloqueio irredutível honesto; 15 leis contínuas, sem promessa de capability/atomicidade, sem ampliar ZeroHITL ou remover gates. |
| 3.5.1 | 2026-11-18 | PRM138 v8.0.0: acrescenta 10 (coownership E2E), 11 (UVD binário separado de WIP) e 12 (StorageLocator, seis metadados e ORPH01–10 como especificação local, sem ADR atribuído). Preserva 1–9, 13–14 e gates humanos; ZeroHITL limitado a técnica autorizada. Alias adaptador versionado; revisão independente dos hashes ainda necessária. |
| 3.5.0 | 2026-11-18 | PRM-136: preserva integralmente 1–9; acrescenta 13 (assentos funcionais, caps mínimos, fila 0/1, redirect fail-closed) e 14 (esgotamento autorizado, kit com check/postcheck, HITL e bloqueios reais). Onze leis presentes; 10–12, v3.4.0 e ADRs 048–055 sem fonte comprovada. Alias adaptador versionado, sem duplicar canônico. Candidato sujeito a revisão independente dos hashes entregues. |
| 3.1.0 | 2026-11-17 | Candidato PRM-121, pendente de revisão independente: Lei 9 (barramento de entrada única sem copy-paste, com espera não disruptiva e fallback de autenticação no pré-voo); Lei 2 conta a cota de workers como limite observado; o workflow lê o estado das sessões irmãs pelo relé (Lei 9); tabela de reconciliação com a lista do operador; numeração 1–8 da 3.0.0 preservada. |
| 3.0.0 | 2026-11-17 | EXTEND da v2.1.0 para as 8 leis do operador: farol passa do fim para o topo, com ordem de desempate 🔵 > 🔴 > 🟣 > 🟡 > 🟢; 🟣 passa a significar revisão independente em curso (definido aqui, sem ADR nem fonte externa); §0 só torna o agente mais estrito, nunca relaxa as leis; Lei 2 trata métrica ausente como desconhecida; Lei 4 exige dependência verificável; Lei 5 prende a aprovação ao SHA-256 e recusa exit code sozinho ou rc=0 sem artefato; Leis 6 (staging exato) e 8 (propagação seletiva) novas; antiga Lei 7 vira rotina complementar; description em YAML `>-`; alias com `name` próprio; adiciona workflow, limites, validação, DUED e Refs; remove referências a ADRs sem fonte e identificadores de organização. |
| 2.1.0 | 2026-11-17 | Versão user-scope de origem (7 leis), criada fora deste repositório. |
