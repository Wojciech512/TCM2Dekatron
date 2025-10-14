#!/usr/bin/env bash
set -euo pipefail

# Ten skrypt generuje lokalny root i intermediate CA dla TCM 2.0.
# Uruchamiaj na offline hostcie. Wymaga openssl >= 1.1.

usage() {
  cat <<'EOF'
Użycie: gen-ca.sh [opcje]

Opcje:
  -f, --force   Nadpisz istniejące artefakty CA.
  -h, --help    Wyświetl tę pomoc.
EOF
}

FORCE=0
while ((${#})); do
  case "$1" in
    -f|--force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Nieznana opcja: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v openssl >/dev/null 2>&1; then
  echo "Błąd: openssl nie jest dostępny w PATH" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

WORKDIR="${REPO_ROOT}/tcm/deploy/ca"
OUTPUT="${WORKDIR}/output"
ROOT_DIR="${WORKDIR}/root-ca"
INTERMEDIATE_DIR="${WORKDIR}/intermediate"
CLIENTS_DIR="${WORKDIR}/clients"
CERTS_DIR="${REPO_ROOT}/tcm/deploy/reverse-proxy/certs"
SENTINEL="${OUTPUT}/.generated"

if [[ -f "${SENTINEL}" && ${FORCE} -eq 0 ]]; then
  echo "Artefakty CA już istnieją. Użyj --force aby wygenerować ponownie." >&2
  exit 1
fi

rm -rf "${OUTPUT}" "${ROOT_DIR}" "${INTERMEDIATE_DIR}" "${CLIENTS_DIR}"
mkdir -p "${OUTPUT}" "${ROOT_DIR}" "${INTERMEDIATE_DIR}" "${CLIENTS_DIR}" "${CERTS_DIR}"
rm -f "${CERTS_DIR}/server.crt.pem" \
  "${CERTS_DIR}/server.key.pem" \
  "${CERTS_DIR}/ca-chain.crt" \
  "${CERTS_DIR}/ca-clients.crt" \
  "${CERTS_DIR}/crl.pem"

# 1. Root CA
openssl genrsa -out "${ROOT_DIR}/root.key.pem" 4096
openssl req -x509 -new -nodes -key "${ROOT_DIR}/root.key.pem" \
    -sha384 -days 3650 -out "${ROOT_DIR}/root.crt.pem" \
    -subj "/C=PL/O=TCM Labs/OU=Root CA/CN=TCM Root CA"

# 2. Intermediate CA
openssl genrsa -out "${INTERMEDIATE_DIR}/intermediate.key.pem" 4096
openssl req -new -key "${INTERMEDIATE_DIR}/intermediate.key.pem" \
    -out "${INTERMEDIATE_DIR}/intermediate.csr.pem" \
    -subj "/C=PL/O=TCM Labs/OU=Intermediate CA/CN=TCM Intermediate CA"
openssl x509 -req -in "${INTERMEDIATE_DIR}/intermediate.csr.pem" \
    -CA "${ROOT_DIR}/root.crt.pem" -CAkey "${ROOT_DIR}/root.key.pem" \
    -CAcreateserial -out "${INTERMEDIATE_DIR}/intermediate.crt.pem" \
    -days 1825 -sha384 -extfile <(printf "basicConstraints=CA:TRUE\nkeyUsage=digitalSignature,keyCertSign,cRLSign")

cat "${INTERMEDIATE_DIR}/intermediate.crt.pem" "${ROOT_DIR}/root.crt.pem" > "${OUTPUT}/ca-chain.crt"
cp "${OUTPUT}/ca-chain.crt" "${WORKDIR}/ca-clients.crt"

# 3. Serwer
openssl genrsa -out "${OUTPUT}/server.key.pem" 4096
openssl req -new -key "${OUTPUT}/server.key.pem" -out "${OUTPUT}/server.csr.pem" \
    -subj "/C=PL/O=TCM Labs/OU=Server/CN=tcm.local"
openssl x509 -req -in "${OUTPUT}/server.csr.pem" \
    -CA "${WORKDIR}/intermediate/intermediate.crt.pem" -CAkey "${WORKDIR}/intermediate/intermediate.key.pem" \
    -CAcreateserial -out "${OUTPUT}/server.crt.pem" -days 825 -sha384 \
    -extfile <(printf "subjectAltName=DNS:tcm.local,DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth")

# 4. Uniwersalny klient (Operator/Technik/Serwis)
CLIENT_COMMON_NAME="TCM Universal Client"
CLIENT_ID="universal"
openssl genrsa -out "${CLIENTS_DIR}/${CLIENT_ID}.key.pem" 4096
openssl req -new -key "${CLIENTS_DIR}/${CLIENT_ID}.key.pem" \
    -out "${CLIENTS_DIR}/${CLIENT_ID}.csr.pem" \
    -subj "/C=PL/O=TCM Users/OU=Shared/CN=${CLIENT_COMMON_NAME}"
openssl x509 -req -in "${CLIENTS_DIR}/${CLIENT_ID}.csr.pem" \
    -CA "${INTERMEDIATE_DIR}/intermediate.crt.pem" -CAkey "${INTERMEDIATE_DIR}/intermediate.key.pem" \
    -CAcreateserial -out "${CLIENTS_DIR}/${CLIENT_ID}.crt.pem" -days 730 -sha384 \
    -extfile <(printf "extendedKeyUsage=clientAuth\nsubjectAltName=DNS:${CLIENT_ID}.local")
cat "${CLIENTS_DIR}/${CLIENT_ID}.crt.pem" "${OUTPUT}/ca-chain.crt" > "${CLIENTS_DIR}/${CLIENT_ID}-fullchain.pem"
openssl pkcs12 -export -in "${CLIENTS_DIR}/${CLIENT_ID}-fullchain.pem" \
    -inkey "${CLIENTS_DIR}/${CLIENT_ID}.key.pem" -out "${OUTPUT}/${CLIENT_ID}.p12" -passout pass:Test123!
tar -czf "${OUTPUT}/client-${CLIENT_ID}.tar.gz" \
    -C "${CLIENTS_DIR}" "${CLIENT_ID}.key.pem" "${CLIENT_ID}-fullchain.pem" \
    -C "${OUTPUT}" "${CLIENT_ID}.p12"
rm "${OUTPUT}/${CLIENT_ID}.p12"

# 5. CRL (nowa, kompletna konfiguracja dla openssl ca)
# wymagane pliki bazy CA
: > "${INTERMEDIATE_DIR}/index.txt"
echo 1000 > "${INTERMEDIATE_DIR}/serial"
echo 1000 > "${INTERMEDIATE_DIR}/crlnumber"

cat > "${INTERMEDIATE_DIR}/openssl.cnf" <<EOF
[ ca ]
default_ca = ca_intermediate

[ ca_intermediate ]
dir = ${INTERMEDIATE_DIR}
database = \$dir/index.txt
serial = \$dir/serial
crlnumber = \$dir/crlnumber
default_crl_days = 30
default_md = sha384
private_key = ${INTERMEDIATE_DIR}/intermediate.key.pem
certificate = ${INTERMEDIATE_DIR}/intermediate.crt.pem

[ policy_loose ]
commonName = supplied
EOF

openssl ca -gencrl -config "${INTERMEDIATE_DIR}/openssl.cnf" -out "${OUTPUT}/crl.pem"

install -m 0644 "${OUTPUT}/server.crt.pem" "${CERTS_DIR}/server.crt.pem"
install -m 0600 "${OUTPUT}/server.key.pem" "${CERTS_DIR}/server.key.pem"
install -m 0644 "${OUTPUT}/ca-chain.crt" "${CERTS_DIR}/ca-chain.crt"
install -m 0644 "${WORKDIR}/ca-clients.crt" "${CERTS_DIR}/ca-clients.crt"
install -m 0644 "${OUTPUT}/crl.pem" "${CERTS_DIR}/crl.pem"

touch "${SENTINEL}"

echo "Artefakty CA zapisano w ${OUTPUT} oraz ${CERTS_DIR}."

