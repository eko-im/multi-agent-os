---
name: libras-writing-bridge
description: >
  Use when interpreting written Portuguese from a Deaf Libras user
  (escrita surda, português L2, interlíngua da Libras, topic-comment order,
  infinitive verbs, omitted articles) or when drafting a message in simple
  adult Portuguese for a Deaf reader (reescrever em linguagem simples,
  ponte de escrita Libras). Do not use for video or avatar sign translation,
  to correct a person's writing, or as a substitute for a professional
  Libras interpreter in legal, medical, or official contexts.
version: "0.1.0"
license: MIT
metadata:
  version: "0.1.0"
  family: content-lifecycle
  display_name: "Ponte de Escrita Surda (Libras)"
  dogfood_status: pending-first-cycle
---

# Ponte de Escrita Surda (Libras)

## Overview

Skill de ponte **texto ↔ texto** entre o português padrão de ouvintes e o português escrito com influência da Libras (muitas vezes L2 de quem tem a Libras como L1). O núcleo é interpretar com honestidade e escrever com clareza adulta. Não é tradutor de sinais, não gera avatar e não substitui intérprete.

A Libras é língua natural, com gramática própria — não é “português com as mãos” (Lei 10.436/2002). Marcas na escrita são lidas como transferência e interlíngua, não como erro, descuido ou déficit. Não existe um único “padrão surdo”: a escolaridade, a idade de acesso à Libras e o canal (mensagem curta vs. texto formal) variam. Declare incerteza quando o enunciado admitir mais de uma leitura.

## When to Use

- **Ler:** chegou (ou vai ser lida) uma mensagem escrita de pessoa surda e o ouvinte precisa do sentido provável.
- **Escrever:** um ouvinte precisa redigir uma mensagem para pessoa surda, em português claro.

**When NOT to use**

- Traduzir vídeo em Libras, gerar glosa como produto principal ou acionar avatar (um serviço opcional de avatar de Libras só entra como anexo ao rascunho).
- “Ensinar português”, revisar a escrita da pessoa como prova ou devolver uma versão “certinha” da mensagem original.
- Assunto jurídico, médico, escolar oficial ou outro ato formal: produza no máximo um rascunho de apoio e recomende intérprete profissional de Libras. A skill não fala em nome da comunidade surda.

## Guardrails (antes de qualquer saída)

1. **Só rascunho, nunca envio.** Quem envia é a pessoa humana, pelo fluxo de rascunho aprovado. Não envie e-mail, mensagem, comentário nem post.
2. **Metacognição de PII e segredos.** Antes de cada saída, procure senhas, tokens, números de documento, dados de saúde e dados de terceiros. Se encontrar: aponte o *tipo* (“há um número de documento”, “há um token”) e **não repita o valor**. Não copie o dado para logs, exemplos, issues, PRs ou memória de treino. Exemplos desta skill são sempre sintéticos e rotulados.
3. **Respeito.** Tom adulto. Não infantilize (sem diminutivo forçado, sem excesso de emoji, sem caixa alta de aviso). Prefira “pessoa surda” / “surdo”, não eufemismos. Não julgue a escrita e não a use como evidência de incapacidade.
4. **Não invente.** Não complete história, não adivinhe motivo ou sentimento, não afirme o que o texto não permite afirmar.
5. **Heterogeneidade.** Não assuma que toda pessoa surda escreve ou prefere o mesmo registro. O modo escrever começa simples e só aprofunda a adaptação se faltar clareza ou se pedirem o registro `interlingua`.

## Modo `ler` (surdo → ouvinte)

Entrada: o texto escrito e, se houver, canal e assunto — sem pedir dados pessoais extras.

Heurísticas (não são regras cegas):

| Traço frequente de L2 | Como costuma aparecer | O que isso *pode* indicar |
|---|---|---|
| Ordem tópico-comentário | Elemento tematizado no início, depois o comentário (“Livro eu ler já”) | O tópico é o tema; o comentário traz o predicação. A ordem básica da Libras é com frequência SVO, com topicalização produtiva — não tratar como “SOV obrigatório”. |
| Verbo pouco flexionado | Infinitivo ou forma não flexionada | Tempo e pessoa podem estar no advérbio ou no contexto, não na desinência. |
| Tempo/aspecto lexical | “já”, “ontem”, “amanhã”, “passado”, “futuro”, “ainda” | Use esses itens para situar o evento; não “corrija” a flexão. |
| Omissão de artigo, preposição ou conectivo | Blocos justapostos, pouca coesão explícita | A relação (causa, tempo, pedido, relato) pode ser ambígua — liste alternativas. |
| Omissão de ser / estar / ficar | Sintagma nominal ou adjetivo sem verbo de ligação | Pode ser estado, identificação ou localização; não invente o verbo se mudar o sentido. |
| Frases curtas, vocabulário de conteúdo | Organização por blocos, pouca subordinação | Leia pelos blocos. Variação ortográfica interpreta-se por contexto, sem relatório de erros. |

Saída obrigatória, nesta ordem:

```
# Leitura (rascunho — não é correção e não foi enviado)

**Interpretação:** <português padrão, só o que o texto permite afirmar>
**Confiança:** alto | médio | baixo   (por enunciado, não só no texto inteiro)
**Traços de L2 observados:** <lista curta, descritiva, sem juízo>
**Ambiguidades e leituras alternativas:** <ou "nenhuma relevante">
**O que o texto não diz:** <o que você se recusou a completar>
**PII / segredos:** nenhum encontrado | apontado o tipo, valor omitido
```

Confiança baixa: diga o que a pessoa operadora deve confirmar e não redija resposta de conteúdo enquanto a leitura não for confirmada. Se pedirem resposta antes disso, o único rascunho permitido é um pedido de esclarecimento (qual das leituras vale). Não use a skill `proofread` sobre o texto original da pessoa.

## Modo `escrever` (ouvinte → destinatário surdo)

Dois registros; o padrão é `simples`. `interlingua` só entra se a pessoa operadora ou a destinatária pedirem.

**Registro `simples` (padrão):** português L2-simples / linguagem simples, adulto e direto.

- Frases curtas; uma ideia por frase; ordem direta (quem faz + ação + complemento); voz ativa.
- Vocabulário concreto. Explique termo técnico na primeira ocorrência. Sigla por extenso na primeira vez.
- Sem expressão idiomática, ironia, sarcasmo ou duplo sentido. Use o léxico em `references/lexico.md` (expressões → equivalente direto, formalismos → palavra simples). Não aplique o pacote de emojis nem títulos em caixa alta.
- Conectivos explícitos quando a relação importar (“por isso”, “se”, “antes”, “depois”).
- Datas, horas, valores e prazos com número, unidade e referente. Confirme entendimento com pergunta simples quando o assunto for horário, valor, endereço ou decisão.
- Sem infantilizar.

**Registro `interlingua` (opt-in):** ritmo mais próximo da transferência da Libras (tópico-comentário, menos artigos, verbo no infinitivo, tempo por advérbio). Nunca é o padrão.

Toda saída traz, nesta ordem:

```
# Rascunho (não enviado)

**Registro:** simples | interlingua (opt-in)
**Rascunho:**
<texto>

**O que foi simplificado ou omitido:** <nota de fidelidade>
**Confirmar com a pessoa:** <data, hora, valor, lugar, sim/não — ou "nada pendente">
**Palavras-chave (opcional):** <substantivos e verbos de conteúdo que podem ter sinal em Libras; não descreva o sinal se não tiver fonte. Isto não é glosa.>
**Anexo opcional:** <link para leitura em um serviço de avatar de Libras, com o aviso de que avatar não substitui o texto nem o intérprete — ou omita>
**PII / segredos:** nenhum encontrado | apontado o tipo, valor omitido
**Limite:** <se o assunto for jurídico, médico ou oficial, recomende intérprete>
```

Ajuste a intensidade: quem já lê português formal com fluência não precisa de reescrita pesada.

## Exemplos (todos criados)

Os blocos abaixo são **exemplos criados** para esta skill. Não são mensagens reais e não descrevem pessoa alguma.

**Exemplo criado 1 — modo ler, confiança alta** (tópico-comentário + infinitivo + “já”).

- Entrada: `Livro eu ler já.`
- Interpretação: “Eu já li o livro.”
- Confiança: alta. Ambiguidades: nenhuma relevante.
- Traços: tópico “livro” à frente; verbo no infinitivo; aspecto com “já”.

**Exemplo criado 2 — modo ler, confiança média** (justaposição sem conectivo).

- Entrada: `Amanhã médico eu ir 14 horas documento falta.`
- Interpretação principal: “Amanhã, às 14 horas, vou ao médico; está faltando algum documento.”
- Confiança: média.
- Ambiguidades: (a) “documento falta” pode ser o que a pessoa precisa levar ou o que o consultório ainda não tem; (b) “médico” pode ser consulta, exame ou encontro com uma pessoa. O rascunho de resposta não inventa qual documento é.

**Exemplo criado 3 — modo ler, confiança baixa** (várias relações possíveis).

- Entrada: `Reunião trabalho chefe bravo projeto atrasar.`
- Candidata A: “Na reunião do trabalho o chefe ficou bravo porque o projeto atrasou.”
- Candidata B: “Há reunião do trabalho; o chefe está bravo; o projeto vai atrasar.”
- Confiança: baixa. Marque A e B e peça contexto antes de redigir resposta.

**Exemplo criado 4 — modo escrever, registro `simples` (padrão).**

- Texto de ouvinte: “Tendo em vista o imprevisto de hoje, peço a gentileza de reagendarmos o almoço para a próxima terça, se estiver tudo bem para você.”
- Rascunho (simples): “O almoço de hoje precisa mudar de dia. Pode ser terça que vem? Se não puder, me avise.”
- Nota de perda: saiu o tom formal (“tendo em vista”, “peço a gentileza”); o pedido e a condição foram preservados. Não enviado.
- Palavras-chave (opcional): almoço, terça.

**Exemplo criado 5 — o que não fazer (infantilizar) e o opt-in `interlingua`.**

O mesmo conteúdo do exemplo 4 **não** deve sair como um aviso em caixa alta cheio de emoji. Isso é barulho, não respeito.

Registro `interlingua`, só se pedido: “Almoço hoje não poder. Terça que vem poder? Se não, você avisar.”

**Exemplo criado 6 — PII / segredo.**

Se a entrada trouxer senha, token ou número de documento, o rascunho aponta o tipo e omite o valor (“Há um número de documento na mensagem. Não repito o valor aqui.”). Não invente nem reproduza o número.

## Common Mistakes

| Desvio | O que fazer |
|---|---|
| Enviar a mensagem direto | Parar. Devolver só o rascunho. |
| “Corrigir” a escrita no modo ler | Interpretar para o ouvinte; não devolver versão normativa da original. |
| Infantilizar com caixa alta, diminutivo ou excesso de emoji | Usar o registro `simples`, tom adulto. |
| Imitar a interlíngua por padrão | `interlingua` é opt-in. |
| Completar o que o texto não diz | Declarar ambiguidade e, se a confiança for baixa, perguntar. |
| Tratar toda pessoa surda como um único padrão | Medir confiança; calibrar a reescrita. |
| Usar a skill no lugar de intérprete em contexto oficial | Recomendar intérprete profissional. |
| Copiar texto real para exemplo, teste, PR ou log | Só exemplos sintéticos. Redigir PII e segredos. |
| Aplicar `proofread` na mensagem original | No modo ler, não. No modo escrever, revise clareza, não “norma máxima”. |

## Limites

Esta skill não lê vídeo de sinais, não certifica glosa e não substitui intérprete profissional de Libras em contexto jurídico, médico, escolar oficial ou outro ato formal. Nesses casos, o rascunho deve dizer isso com clareza. Complementos de avatar ou glosa, se usados, ficam anexos ao rascunho e carregam o mesmo aviso.

## Proveniência

O léxico de expressões e simplificações e as regras gerais de clareza (frases curtas, sem idioma nem sarcasmo) foram reaproveitados da skill `libras-accessibility` do projeto Akasha Ekora (licença MIT): `skills/libras-accessibility/src/index.ts` e `skills/libras-accessibility/SKILL.md`. O mapa de emojis, a formatação em caixa alta, testes e quaisquer artefatos pessoais daquela origem **não** foram portados. Detalhe e tabelas: `references/lexico.md`.
