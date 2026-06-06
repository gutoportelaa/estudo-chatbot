#!/usr/bin/env bash
#
# Demonstra o isolamento de histórico entre sessões de usuários diferentes.
#
# Cria duas sessões (A e B), ensina um fato apenas para a A e mostra que:
#   - a sessão A LEMBRA o fato (mesmo thread_id);
#   - a sessão B NÃO tem acesso a ele (thread_id diferente).
#
# Uso:  API_URL=http://localhost:8000 ./scripts/demo_sessions.sh
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

new_session() {
  curl -s -X POST "$API_URL/session" | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])"
}

# Envia uma mensagem e imprime a resposta já "desmontada" do formato SSE.
ask() {
  local sid="$1" msg="$2"
  curl -s -N -X POST "$API_URL/chat" \
    -H 'Content-Type: application/json' \
    -d "{\"session_id\":\"$sid\",\"message\":\"$msg\"}" \
    | sed 's/^data: //' | grep -v '^\[DONE\]$' | tr -d '\n' | sed 's/\\n/ /g'
  echo
}

echo "API: $API_URL"
SID_A="$(new_session)"
SID_B="$(new_session)"
echo "Sessão A: $SID_A"
echo "Sessão B: $SID_B"
echo

echo "── [A] Ensina um fato ──────────────────────────────"
echo "A> Meu nome é Gutemberg e minha cor favorita é verde. Responda apenas OK."
echo -n "ThinkAI(A)> "; ask "$SID_A" "Meu nome é Gutemberg e minha cor favorita é verde. Responda apenas OK."
echo

echo "── [A] Recupera o fato (deve lembrar) ──────────────"
echo "A> Qual é o meu nome e minha cor favorita?"
echo -n "ThinkAI(A)> "; ask "$SID_A" "Qual é o meu nome e minha cor favorita?"
echo

echo "── [B] Mesma pergunta em outra sessão (NÃO deve saber) ──"
echo "B> Qual é o meu nome e minha cor favorita?"
echo -n "ThinkAI(B)> "; ask "$SID_B" "Qual é o meu nome e minha cor favorita?"
echo

echo "── Histórico persistido de cada sessão (GET /history) ──"
echo "A:"; curl -s "$API_URL/history/$SID_A" | python3 -m json.tool
echo "B:"; curl -s "$API_URL/history/$SID_B" | python3 -m json.tool
