#!/usr/bin/env bash
set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for this script" >&2
  exit 1
fi

API_BASE=${API_BASE:-http://127.0.0.1:8000}
TS=$(date +%s)
RAND=$(python - <<'PY'
import secrets
print(secrets.token_hex(3))
PY
)
OWNER_EMAIL="owner+${TS}${RAND}@test.com"
FINDER_EMAIL="finder+${TS}${RAND}@test.com"
PASSWORD="Passw0rd!${RAND}${TS}"

pretty() {
  if [[ $# -gt 0 ]]; then
    jq . <<<"$1"
  else
    jq .
  fi
}

post_json() {
  local path=$1
  local body=$2
  shift 2
  curl -sS -X POST "${API_BASE}${path}" \
    -H 'content-type: application/json' \
    "$@" \
    --data-raw "${body}"
}

patch_json() {
  local path=$1
  local body=$2
  shift 2
  curl -sS -X PATCH "${API_BASE}${path}" \
    -H 'content-type: application/json' \
    "$@" \
    --data-raw "${body}"
}

get_json() {
  local path=$1
  shift
  curl -sS "${API_BASE}${path}" "$@"
}

echo "==> health check"
get_json "/healthz" | pretty

echo "==> signup users"
owner_signup=$(jq -n \
  --arg email "$OWNER_EMAIL" \
  --arg password "$PASSWORD" \
  --arg name "Owner ${TS}" \
  '{email:$email, password:$password, display_name:$name}')
pretty "$(post_json "/auth/signup" "$owner_signup")"

finder_signup=$(jq -n \
  --arg email "$FINDER_EMAIL" \
  --arg password "$PASSWORD" \
  --arg name "Finder ${TS}" \
  '{email:$email, password:$password, display_name:$name}')
pretty "$(post_json "/auth/signup" "$finder_signup")"

echo "==> login"
login_body_owner=$(jq -n --arg email "$OWNER_EMAIL" --arg password "$PASSWORD" '{email:$email,password:$password}')
OWNER_TOKEN=$(post_json "/auth/login" "$login_body_owner" | jq -r .access_token)

login_body_finder=$(jq -n --arg email "$FINDER_EMAIL" --arg password "$PASSWORD" '{email:$email,password:$password}')
FINDER_TOKEN=$(post_json "/auth/login" "$login_body_finder" | jq -r .access_token)

if [[ -z "$OWNER_TOKEN" || "$OWNER_TOKEN" == "null" ]]; then
  echo "Owner login failed" >&2
  exit 2
fi
if [[ -z "$FINDER_TOKEN" || "$FINDER_TOKEN" == "null" ]]; then
  echo "Finder login failed" >&2
  exit 2
fi

echo "==> finder posts found item"
found_payload=$(jq -n \
  '{
    title: "Blue Hydro Flask",
    description: "Found a blue Hydro Flask near the library study rooms.",
    tags: ["hydroflask", "blue"],
    location: {zone: "Library"},
    when: "2025-09-05T14:00:00Z",
    category: "water_bottle",
    photos: [
      {
        url: "http://minio:9000/lfs-media/example.jpg",
        thumbnails: [],
        safety: {facesBlurred: true, piiRedacted: true}
      }
    ],
    verificationPrompts: ["What sticker is on the lid?"]
  }')
FOUND_ITEM=$(post_json "/items/found" "$found_payload" -H "authorization: Bearer ${FINDER_TOKEN}")
pretty "${FOUND_ITEM}"
FOUND_ID=$(jq -r .id <<<"${FOUND_ITEM}")

if [[ -z "$FOUND_ID" || "$FOUND_ID" == "null" ]]; then
  echo "Failed to create found item" >&2
  exit 3
fi

echo "==> owner posts lost item"
lost_payload=$(jq -n \
  '{
    title: "My Blue Hydro Flask",
    description: "Blue bottle with a wolf sticker on the lid.",
    tags: ["hydroflask", "blue"],
    location: {zone: "Library"},
    when: "2025-09-05T13:00:00Z",
    category: "water_bottle",
    photos: []
  }')
LOST_ITEM=$(post_json "/items/lost" "$lost_payload" -H "authorization: Bearer ${OWNER_TOKEN}")
pretty "${LOST_ITEM}"
LOST_ID=$(jq -r .id <<<"${LOST_ITEM}")

if [[ -z "$LOST_ID" || "$LOST_ID" == "null" ]]; then
  echo "Failed to create lost item" >&2
  exit 4
fi

sleep 1

echo "==> request matches"
MATCHES=$(get_json "/matches" -G --data-urlencode "itemId=${LOST_ID}" --data-urlencode "k=5")
pretty "${MATCHES}"
CANDIDATE_ID=$(jq -r '.[0].candidateId' <<<"${MATCHES}")

if [[ -z "$CANDIDATE_ID" || "$CANDIDATE_ID" == "null" ]]; then
  echo "No match candidates returned" >&2
  exit 5
fi

echo "==> owner opens claim"
claim_payload=$(jq -n \
  --arg lost "$LOST_ID" \
  --arg candidate "$CANDIDATE_ID" \
  '{
    itemId: $lost,
    candidateId: $candidate,
    answers: [
      {question: "Describe any stickers or markings on the bottle.", answer: "Wolf sticker"},
      {question: "What size or capacity is the bottle?", answer: "21 oz"},
      {question: "What sticker is on the lid?", answer: "Wolf"}
    ]
  }')
CLAIM=$(post_json "/claims" "$claim_payload" -H "authorization: Bearer ${OWNER_TOKEN}")
pretty "${CLAIM}"
CLAIM_ID=$(jq -r .id <<<"${CLAIM}")

if [[ -z "$CLAIM_ID" || "$CLAIM_ID" == "null" ]]; then
  echo "Failed to open claim" >&2
  exit 6
fi

echo "==> finder verifies claim"
verify_payload=$(jq -n '{action: "verify"}')
pretty "$(patch_json "/claims/${CLAIM_ID}" "$verify_payload" -H "authorization: Bearer ${FINDER_TOKEN}")"

echo "==> fetch claim"
pretty "$(get_json "/claims/${CLAIM_ID}" -H "authorization: Bearer ${OWNER_TOKEN}")"

echo "==> done"
