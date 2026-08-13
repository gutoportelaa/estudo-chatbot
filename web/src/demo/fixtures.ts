/**
 * Dados de exemplo do modo demo (GitHub Pages).
 * ---------------------------------------------------------------------------
 * Nada aqui vem de um usuário real: são documentos, conversas e métricas
 * fabricados só para a vitrine estática, onde não existe backend.
 */

import type {
  AuthUser,
  ChatMessage,
  DocumentItem,
  SessionSummary,
  SummaryItem,
  UsageSummary,
} from "../api/client";

export const DEMO_USER: AuthUser = {
  id: "demo-user",
  username: "visitante",
  full_name: "Visitante da demo",
  email: "demo@thinkai.dev",
  description: "Explorando o ThinkAI em modo demonstração.",
  has_avatar: false,
  created_at: "2026-06-01T12:00:00Z",
};

const hoursAgo = (h: number) => new Date(Date.now() - h * 36e5).toISOString();

export const DEMO_DOCUMENTS: DocumentItem[] = [
  { id: "d1", filename: "Build a Large Language Model From Scratch.pdf", size_bytes: 7_453_543, page_count: 370 },
  { id: "d2", filename: "Gemini Embedding 2 — Technical Report.pdf", size_bytes: 1_257_219, page_count: 24 },
  { id: "d3", filename: "Computer Vision — A Modern Approach.pdf", size_bytes: 3_606_983, page_count: 793 },
  { id: "d4", filename: "Web Scraping para Coleta de Dados.pdf", size_bytes: 3_126_960, page_count: 18 },
  { id: "d5", filename: "Atenção é tudo que você precisa (Transformers).pdf", size_bytes: 2_214_880, page_count: 15 },
  { id: "d6", filename: "Padrões de Projeto — Notas de Aula.pdf", size_bytes: 984_120, page_count: 52 },
].map((d, i) => ({
  ...d,
  extraction_status: "done" as const,
  // Sem capa: o modo demo não embute imagens dos PDFs, e a UI já tem fallback.
  has_thumbnail: false,
  created_at: hoursAgo((i + 1) * 9),
}));

export const DEMO_SESSIONS: SessionSummary[] = [
  { id: "s1", title: "Como funciona o mecanismo de atenção", created_at: hoursAgo(30), updated_at: hoursAgo(3) },
  { id: "s2", title: "Resumo: embeddings multimodais", created_at: hoursAgo(52), updated_at: hoursAgo(20) },
  { id: "s3", title: "Dúvidas sobre backpropagation", created_at: hoursAgo(74), updated_at: hoursAgo(49) },
  { id: "s4", title: "Plano de estudos — visão computacional", created_at: hoursAgo(96), updated_at: hoursAgo(70) },
];

const ATTENTION_ANSWER = `Cada token olha para **todos os outros tokens** da sequência ao mesmo tempo e
decide, por pesos aprendidos, de quais deles precisa para se representar melhor.

| Vetor | Papel | Intuição |
|---|---|---|
| **Q** (query) | o que este token procura | "preciso de um sujeito" |
| **K** (key) | o que este token oferece | "eu sou um sujeito" |
| **V** (value) | o conteúdo transportado | a informação em si |

\`\`\`python
scores  = (Q @ K.T) / math.sqrt(d_k)
weights = torch.softmax(scores, dim=-1)
output  = weights @ V
\`\`\`

**Por que superou as RNNs:** a recorrência processa token a token, enquanto a
atenção calcula a matriz inteira de uma vez (paralelismo na GPU) e liga o token 1
ao token 500 em *um* passo, sem dissipar o gradiente.`;

export const DEMO_MESSAGES: Record<string, ChatMessage[]> = {
  s1: [
    {
      id: "m1",
      role: "user",
      content: "Explique o mecanismo de self-attention usando o PDF que anexei. Por que ele substituiu as RNNs?",
    },
    {
      id: "m2",
      role: "assistant",
      content: ATTENTION_ANSWER,
      sources: [
        {
          kind: "rag",
          title: "Atenção é tudo que você precisa (Transformers).pdf",
          snippet: "The Transformer allows for significantly more parallelization…",
          score: 0.91,
          document_id: "d5",
          chunk_index: 3,
          page: 2,
        },
        {
          kind: "rag",
          title: "Build a Large Language Model From Scratch.pdf",
          snippet: "Scaled dot-product attention divides by the square root of the key dimension…",
          score: 0.87,
          document_id: "d1",
          chunk_index: 42,
          page: 61,
        },
        {
          kind: "web",
          title: "The Illustrated Transformer — Jay Alammar",
          url: "https://jalammar.github.io/illustrated-transformer/",
          snippet: "A visual walkthrough of queries, keys and values.",
          score: 0.78,
        },
      ],
    },
  ],
  s2: [
    { id: "m3", role: "user", content: "Resuma as contribuições do relatório do Gemini Embedding 2." },
    {
      id: "m4",
      role: "assistant",
      content: `O relatório apresenta um modelo de **embedding multimodal nativo**, treinado a
partir do próprio Gemini em vez de um encoder separado.

- Um mesmo espaço vetorial cobre **texto, imagem e vídeo**, dispensando modelos por modalidade.
- **Matryoshka representation learning** permite truncar o vetor sem retreinar, trocando custo por precisão.
- Ganhos consistentes em recuperação multilíngue frente à geração anterior.`,
      sources: [
        {
          kind: "rag",
          title: "Gemini Embedding 2 — Technical Report.pdf",
          snippet: "a native multimodal embedding model that allows embedding of text, image and video…",
          score: 0.94,
          document_id: "d2",
          chunk_index: 1,
          page: 1,
        },
      ],
    },
  ],
  s3: [],
  s4: [],
};

export const DEMO_SUMMARIES: SummaryItem[] = [
  {
    id: "r1",
    kind: "single",
    llm_model: "gemini-2.0-flash",
    content: "Resumo do capítulo sobre atenção…",
    document_ids: ["d5"],
    created_at: hoursAgo(5),
  },
  {
    id: "r2",
    kind: "consolidated",
    llm_model: "gemini-2.0-flash",
    content: "Comparativo entre os três artigos…",
    document_ids: ["d1", "d2", "d5"],
    created_at: hoursAgo(22),
  },
  {
    id: "r3",
    kind: "single",
    llm_model: "llama3.2:3b",
    content: "Notas sobre web scraping…",
    document_ids: ["d4"],
    created_at: hoursAgo(46),
  },
];

export const DEMO_DOC_SUMMARY: SummaryItem = {
  id: "sm1",
  kind: "single",
  llm_model: "gemini-2.0-flash",
  document_ids: ["d5"],
  created_at: hoursAgo(4),
  content: `O artigo propõe o **Transformer**, a primeira arquitetura de tradução a
dispensar por completo recorrência e convoluções, apoiando-se apenas em atenção.

- **Atenção multi-cabeça** permite atender a subespaços de representação distintos em paralelo.
- **Codificação posicional senoidal** injeta a ordem dos tokens sem recorrência.
- Alcançou **28,4 BLEU** em WMT 2014 inglês→alemão, treinando em uma fração do tempo dos modelos anteriores.`,
};

export const DEMO_MINDMAP: SummaryItem = {
  id: "mm1",
  kind: "single",
  llm_model: "gemini-2.0-flash",
  document_ids: ["d5"],
  created_at: hoursAgo(4),
  content: `# Transformers

## Arquitetura
### Encoder
#### Self-attention multi-cabeça
#### Feed-forward posicional
### Decoder
#### Atenção mascarada
#### Cross-attention
### Codificação posicional
#### Senoidal
#### Aprendida

## Mecanismo de atenção
### Query, Key, Value
### Produto escalar escalado
### Softmax dos pesos
### Múltiplas cabeças

## Vantagens
### Paralelismo na GPU
### Dependências de longo alcance
### Pesos interpretáveis

## Limitações
### Custo quadrático O(n²)
### Janela de contexto finita
`,
};

function buildUsage(): UsageSummary {
  const today = new Date();
  const by_day = Array.from({ length: 30 }, (_, i) => {
    const d = new Date(today.getTime() - (29 - i) * 864e5);
    const base = 9000 + Math.round(6500 * Math.sin(i / 3.1) ** 2) + i * 220;
    return {
      date: d.toISOString().slice(0, 10),
      requests: 8 + (i % 7) * 3,
      input_tokens: base,
      output_tokens: Math.round(base * 0.42),
      cost_usd: base * 0.0000021,
      errors: i % 11 === 0 ? 1 : 0,
    };
  });
  const sum = (k: keyof (typeof by_day)[number]) =>
    by_day.reduce((acc, d) => acc + (d[k] as number), 0);

  return {
    days: 30,
    totals: {
      requests: sum("requests"),
      input_tokens: sum("input_tokens"),
      output_tokens: sum("output_tokens"),
      cost_usd: sum("cost_usd"),
      avg_latency_ms: 1240,
      errors: sum("errors"),
      success_rate: 0.978,
      rag_requests: 143,
    },
    by_day,
    by_model: [
      { model: "gemini-2.0-flash", requests: 402, input_tokens: 318_400, output_tokens: 131_900, cost_usd: 0.6842 },
      { model: "llama3.2:3b (ollama)", requests: 118, input_tokens: 74_200, output_tokens: 30_100, cost_usd: 0 },
      { model: "gpt-oss-120b (groq)", requests: 41, input_tokens: 22_800, output_tokens: 9_400, cost_usd: 0.0512 },
    ],
    recent_errors: [
      { created_at: hoursAgo(39), model: "gemini-2.0-flash", error: "429 Resource exhausted (rate limit do tier gratuito)" },
      { created_at: hoursAgo(160), model: "gemini-2.0-flash", error: "503 Model overloaded, tente novamente" },
    ],
  };
}

export const DEMO_USAGE = buildUsage();

export const DEMO_CONTEXT = {
  model: "gemini-2.0-flash",
  input_tokens: 6432,
  output_tokens: 918,
  breakdown: { system: 412, summary: 1180, rag: 3120, recent: 1520, tool: 200 },
  created_at: hoursAgo(3),
};

export const DEMO_SUMMARY_EVENTS = [
  {
    id: "e1",
    covered_message_count: 24,
    source_message_count: 30,
    summary_tokens: 1180,
    trigger: "window_overflow",
    model: "gemini-2.0-flash",
    created_at: hoursAgo(3),
  },
];

/** Resposta canned para qualquer pergunta nova feita na demo. */
export const DEMO_FALLBACK_REPLY = `Esta é uma **demonstração estática** do ThinkAI, publicada no GitHub Pages —
não há backend nem modelo de linguagem por trás desta resposta.

Na aplicação real, esta mensagem seria enviada a um LLM (Gemini, Groq, OpenRouter
ou Ollama) junto de um contexto montado sob orçamento de tokens, com trechos
recuperados dos seus PDFs por busca vetorial e a citação da página de origem.

Explore as conversas já existentes na barra lateral, a **Biblioteca** e a tela de
**Consumo** para ver esses recursos com dados de exemplo.`;
