#!/usr/bin/env bash
#
# Demonstra o isolamento de histórico entre sessões de usuários diferentes.
#
# Cria duas contas (A e B), faz login, cria sessões e demonstra que:
#   - a sessão A LEMBRA o fato (mesmo thread_id);
#   - a sessão B NÃO tem acesso a ele (thread_id e contas diferentes).
#
# Uso:  API_URL=http://localhost:8000 ./scripts/demo_sessions.sh
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

# Gera nomes únicos para evitar colisões no banco de dados
USER_A="user_A_$(date +%s)"
USER_B="user_B_$(date +%s)"
PASS="senha123"

echo "API: $API_URL"
echo "── [1] Criando contas ────────────────────────────────────"
curl -s -X POST "$API_URL/auth/signup" -H 'Content-Type: application/json' -d "{\"username\":\"$USER_A\",\"password\":\"$PASS\"}" > /dev/null
curl -s -X POST "$API_URL/auth/signup" -H 'Content-Type: application/json' -d "{\"username\":\"$USER_B\",\"password\":\"$PASS\"}" > /dev/null
echo "Usuário A: $USER_A"
echo "Usuário B: $USER_B"
echo

echo "── [2] Autenticando (Pegando tokens) ─────────────────────"
TOKEN_A=$(curl -s -X POST "$API_URL/auth/signin" -H 'Content-Type: application/json' -d "{\"username\":\"$USER_A\",\"password\":\"$PASS\"}" | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))")
TOKEN_B=$(curl -s -X POST "$API_URL/auth/signin" -H 'Content-Type: application/json' -d "{\"username\":\"$USER_B\",\"password\":\"$PASS\"}" | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$TOKEN_A" ] || [ -z "$TOKEN_B" ]; then
    echo "Erro ao autenticar! Verifique se a API está rodando."
    exit 1
fi
echo "Tokens recebidos com sucesso."
echo

new_session() {
  local token="$1"
  # Tenta /sessions e se falhar /session (para retrocompatibilidade com versão anterior)
  local sid
  sid=$(curl -s -X POST "$API_URL/sessions" -H "Authorization: Bearer $token" | python3 -c "import sys,json;print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
  if [ -z "$sid" ]; then
      sid=$(curl -s -X POST "$API_URL/session" -H "Authorization: Bearer $token" | python3 -c "import sys,json;print(json.load(sys.stdin).get('session_id',''))")
  fi
  echo "$sid"
}

echo "── [3] Criando Sessões ───────────────────────────────────"
SID_A="$(new_session "$TOKEN_A")"
SID_B="$(new_session "$TOKEN_B")"

echo "Sessão A ($USER_A): $SID_A"
echo "Sessão B ($USER_B): $SID_B"
echo

# Envia uma mensagem e imprime a resposta já "desmontada" do formato SSE.
ask() {
  local sid="$1" msg="$2" token="$3"
  curl -s -N -X POST "$API_URL/chat" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $token" \
    -d "{\"session_id\":\"$sid\",\"message\":\"$msg\"}" \
    | sed 's/^data: //' | grep -v '^\[DONE\]$' | tr -d '\n' | sed 's/\\n/ /g'
  echo
}

echo "── [A] Ensina um fato ──────────────────────────────"
echo "A> Meu nome é Gutemberg e minha cor favorita é verde. Responda apenas OK."
echo -n "ThinkAI(A)> "; ask "$SID_A" "Meu nome é Gutemberg e minha cor favorita é verde. Responda apenas OK." "$TOKEN_A"
echo

echo "── [A] Recupera o fato (deve lembrar) ──────────────"
echo "A> Qual é o meu nome e minha cor favorita?"
echo -n "ThinkAI(A)> "; ask "$SID_A" "Qual é o meu nome e minha cor favorita?" "$TOKEN_A"
echo

echo "── [B] Mesma pergunta em outra sessão (NÃO deve saber) ──"
echo "B> Qual é o meu nome e minha cor favorita?"
echo -n "ThinkAI(B)> "; ask "$SID_B" "Qual é o meu nome e minha cor favorita?" "$TOKEN_B"
echo

echo "── Histórico persistido de cada sessão (GET /history) ──"
echo "A:"; curl -s "$API_URL/history/$SID_A" -H "Authorization: Bearer $TOKEN_A" | python3 -m json.tool
echo "B:"; curl -s "$API_URL/history/$SID_B" -H "Authorization: Bearer $TOKEN_B" | python3 -m json.tool
