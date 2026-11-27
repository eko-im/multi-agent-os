# EXORDIUM — Protocolo de Ciclo de Vida do Diálogo (humano ↔ agente ↔ humano)

> **Version**: 0.1.0 · **Date**: 2026-10-26 · **Status**: Proposed (HITL-ratify via PR)
> **Etimologia**: lat. *exordium* — "o começo da urdidura" (ex- + ordiri, tecer); de
> *ordiri* vem **ordem** e **oratória**. Um diálogo é um tecido que se começa, se tece e se arremata.
> **Linhagem**: nasce da diretriz do operador (2026-10-26): protocolo de comunicação entre bots
> em nível **filosófico/metodológico** (handshake → apresentação → meio → finalização), legível
> por humanos e operável por agentes — não de rede/infraestrutura.
> **DRY**: a sintaxe do envelope compacto bot↔bot já é o [`agent-comm-protocol` (ACP)](agent-comm-protocol.md);
> este protocolo é a **camada pragmática** (significado, fases, atos, epistêmê) que o ACP transporta.
> Reusa também: `skills/pii-masking` (gate), `skills/response-compression` (dose),
> `protocols/agent-delegation` (handoff), `docs/co-author-standard.md` (identidade),
> `skills/agentic-session-harness` (persistência). Não reimplementa nenhum.

## 1. Propósito

Dar a **todo diálogo entre seres (humanos e/ou agentes)** uma estrutura comum de
início, meio e fim, com taxonomia fechada de intenções e marcadores epistêmicos, de modo que:

1. um **humano** leia e entenda sem esforço extra (o protocolo não atrapalha a conversa);
2. um **agente** execute cada fase deterministicamente (o protocolo é lei operável);
3. a **troca entre agentes** no mesmo canal seja rastreável, compacta e sem conversa fiada.

## 2. Fundamentos (as sete lentes)

| Lente | O que governa | Âncora |
|---|---|---|
| **Semiótica** | todo sinal tem forma + conteúdo + interpretante; nada se envia sem os três | Peirce |
| **Taxonomia** | verbos de fala em conjunto FECHADO (art. 5); extensão = major version | Searle |
| **Semântica** | máxima da cooperação: quantidade, qualidade, relevância, modo | Grice |
| **Ontologia** | quem existe na cena: humano, agente, persona, canal, thread — cada um com id | art. 3 |
| **Epistemologia** | toda afirmação carrega confiança e fonte; sem fonte = hipótese | art. 6 |
| **Etimologia** | nomes de fases/atos em latim/grego, auto-explicativos, estáveis entre versões | art. 1 |
| **Cronologia + Semver** | timestamps ISO-8601; protocolo versionado MAJOR.MINOR.PATCH | art. 8 |

## 3. Atores e identidade (regra zero)

Antes de qualquer fase, o agente responde internamente (check de metacognição):

- **Quem sou**: nome da instância + harness + sessão (ex.: `messenger@abacus/s7`).
- **Onde estou**: canal/servidor/thread; quem mais existe na cena (outros bots, humanos).
- **Em nome de quem falo**: por mim mesmo (agente) **ou** pelo operador (persona-proxy).
  Um agente **nunca** fala pelo humano sem certeza ≥90% de autorização (protocolo de segurança).
- **Com quem falo**: id/nome, humano|agente, idioma, conhecido|desconhecido|suspeito;
  decide criar/atualizar o cadastro do indivíduo (KB de contatos).

## 4. As cinco fases (ciclo de vida)

```
DEXIOSIS → PROLOGOS → MESOPRAXIS → PERORATIO → ANAMNESIS
(aperto    (abertura  (tecido do    (fechamento (persistência
 de mãos)   de intenção) assunto)     do acordo)   do que vale)
```

### F1 · DEXIOSIS (handshake / apresentação)
*gr. dexíōsis — o aperto da destra.* Primeiro contato entre seres que não se reconhecem.
- Cada lado emite: `eu=<id> falo=<em nome de quem?> idioma=<x> quero=<verbo+alvo> conf=<0-100>`.
- Reconhecimento prévio (cadastro/KB) ⇒ DEXIOSIS se resume a `re=<thread>` (não se repete).
- **Gate de segurança**: identidade não verificada ⇒ nada de dados privados, nada de ação externa.

### F2 · PROLOGOS (abertura da intenção)
*gr. prólogos — fala preliminar.* Enquadra o porquê do diálogo antes do conteúdo.
- Um `ASSERT` de contexto + um `DIRECT` de objetivo, com `by=` (prazo) quando houver.
- DoR do diálogo: o que precisa ser verdade no fim para ter valido a pena.

### F3 · MESOPRAXIS (o meio, o tecido)
*gr. mésos + praxis — a ação do meio.* Troca de atos de fala (art. 5) em turnos.
- Regra de dose (Grice/quantidade): o mínimo que completa o ato; zero payload ⇒ zero mensagem.
- Regra de visibilidade humana: bot↔bot em envelope `acp` (bloco de código); humano recebe
  prosa no idioma dele, **fora** de qualquer envelope. Agente não responde envelope que não é dele.
- Regra de não-interferência: dois agentes não disputam o mesmo item — `CLAIM`/`YIELD` (ACP).

### F4 · PERORATIO (fechamento do acordo)
*lat. per-oratio — fala final.* Todo diálogo termina com acordo explícito ou divergência registrada.
- Sintetiza: `DECISÃO(what) + RESPONSÁVEL(who) + PRAZO(when) + EVIDÊNCIA(how measured)`.
- Sem fechamento ⇒ o diálogo fica OPEN (nunca "presumido concluído").

### F5 · ANAMNESIS (persistência)
*gr. anámnesis — re-miniscência, "relembrar".* O que serve a mentes amnésicas é gravado.
- Decisões, cadastros novos/atualizados, pendências e evidências vão para memória/ticket/journal.
- O que **não** se persiste: segredos, PII, dados do operador não autorizados (gate pii-masking).

## 5. Taxonomia fechada de atos de fala (o que se pode "fazer com palavras")

Austin/Searle, reduzidos ao mínimo operável. Cada turno de MESOPRAXIS é **exatamente um** ato:

| Ato | força ilocutória | exemplo compacto |
|---|---|---|
| `ASSERT` | afirmar um estado do mundo (com `src=`,`conf=`) | "CI do PR #540 está verde (src=gh pr checks)" |
| `DIRECT` | pedir/ordenar/propor ação a outrem | "rode a avaliação até 15h" |
| `COMMIT` | comprometer-se a agir (cria dívida rastreável) | "eu cuido do draft da resposta" |
| `DECLARE` | mudar estado por enunciação (só com autoridade) | "ticket EKO-178 fechado" |
| `EXPRESS` | atitude (gratidão, alerta, discordância) — payload ≠ 0 | "⚠️ esse merge conflita com a regra 7" |

Regras: `DECLARE` exige autoridade verificável (papel/mandato); agente sem mandato **não declara**,
no máximo `DIRECT` ao operador. `ASK/ACK/RESULT/BLOCKED/NEEDS-OPERATOR/CLAIM/YIELD/DONE` (ACP)
são as **formas de transporte** destes atos entre bots.

## 6. Marcadores epistêmicos (como se sabe o que se afirma)

- `conf=<0-100>` — confiança do emissor na proposição. `<90` ⇒ verbo de ação proibido, só `INFO`/`ASK`.
- `src=<onde medido>` — evidência observável; sem `src`, `ASSERT` degrada para `ASSERT[hyp]` (hipótese).
- `status={fato|inferência|suposição|testemunho}` — o modo de conhecer (epistemologia explícita).
- `em=<nome|proxy|agente>` — a fonte da fala (quem, não apenas o quê).

## 7. Layout e gramática (dual-legibilidade)

- **Para humanos**: prosa natural no idioma do interlocutor (fallback: idioma da thread). O protocolo
  aparece no **fechamento** (resumo who/what/when/evidence), não no meio da conversa.
- **Para agentes**: uma linha por ato, delimitadores `|`, chaves `k=v`, envelope `acp` (sintaxe ACP).
- **Símbolos estáveis** (poucos, universais): `→` consequência/encaminhamento · `⇒` decisão ·
  `⚠️` risco · `🔒` PII/segredo presente (nunca o valor!) · `@` endereçamento · `re=` referência.
- Compactação: `response-compression` escolhe a dose; nunca sacrificar a força do ato por brevidade.

## 8. Versionamento (semver do protocolo)

- **MAJOR** — muda a taxonomia de atos ou o número/fase do ciclo (re-negociação entre agentes).
- **MINOR** — novo campo/marcador retro-compatível; nova lente transversal.
- **PATCH** — clarificação, exemplos, correções editoriais.
- Todo envelope pode carregar `p=exordium/<ver>`; divergência de MAJOR ⇒ `NEEDS-OPERATOR`.
- Cronologia de eventos do diálogo: ISO-8601 com offset local (`2026-10-26T11:42-03:00`).

## 9. Aplicação a si mesmo (self-hosting)

Este documento: tem DEXIOSIS (identidade/linhagem no cabeçalho), PROLOGOS (propósito),
MESOPRAXIS (taxonomia + regras), PERORATIO (status Proposed, pendente de ratificação HITL) e
exige ANAMNESIS (muda só via PR versionado). Obedece suas próprias leis: compacto, taxonomia
fechada, epistêmê explícita, nunca fala pelo humano.

## 10. Ratificação pendente (HITL)

- [ ] Operador revisa nomes das fases e da taxonomia de atos.
- [ ] Decide relação formal com ACP (este doc referencia; ACP transporta).
- [ ] Promove Status: Proposed → Ratified (bump 1.0.0) via PR verde.
