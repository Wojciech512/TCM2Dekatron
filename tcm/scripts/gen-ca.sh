#!/usr/bin/env bash
set -euo pipefail

# Ten skrypt generuje lokalny root i intermediate CA dla TCM 2.0.
# Uruchamiaj na offline hostcie. Wymaga openssl >= 1.1.

WORKDIR="$(pwd)/tcm/deploy/ca"
OUTPUT="${WORKDIR}/output"
mkdir -p "${OUTPUT}" "${WORKDIR}/root-ca" "${WORKDIR}/intermediate" "${WORKDIR}/clients"

# 1. Root CA
openssl genrsa -out "${WORKDIR}/root-ca/root.key.pem" 4096
openssl req -x509 -new -nodes -key "${WORKDIR}/root-ca/root.key.pem" \
    -sha384 -days 3650 -out "${WORKDIR}/root-ca/root.crt.pem" \
    -subj "/C=PL/O=TCM Labs/OU=Root CA/CN=TCM Root CA"

# 2. Intermediate CA
openssl genrsa -out "${WORKDIR}/intermediate/intermediate.key.pem" 4096
openssl req -new -key "${WORKDIR}/intermediate/intermediate.key.pem" \
    -out "${WORKDIR}/intermediate/intermediate.csr.pem" \
    -subj "/C=PL/O=TCM Labs/OU=Intermediate CA/CN=TCM Intermediate CA"
openssl x509 -req -in "${WORKDIR}/intermediate/intermediate.csr.pem" \
    -CA "${WORKDIR}/root-ca/root.crt.pem" -CAkey "${WORKDIR}/root-ca/root.key.pem" \
    -CAcreateserial -out "${WORKDIR}/intermediate/intermediate.crt.pem" \
    -days 1825 -sha384 -extfile <(printf "basicConstraints=CA:TRUE\nkeyUsage=digitalSignature,keyCertSign,cRLSign")

cat "${WORKDIR}/intermediate/intermediate.crt.pem" "${WORKDIR}/root-ca/root.crt.pem" > "${OUTPUT}/ca-chain.crt"
cp "${OUTPUT}/ca-chain.crt" "${WORKDIR}/ca-clients.crt"

# 3. Serwer
openssl genrsa -out "${OUTPUT}/server.key.pem" 4096
openssl req -new -key "${OUTPUT}/server.key.pem" -out "${OUTPUT}/server.csr.pem" \
    -subj "/C=PL/O=TCM Labs/OU=Server/CN=tcm.local"
openssl x509 -req -in "${OUTPUT}/server.csr.pem" \
    -CA "${WORKDIR}/intermediate/intermediate.crt.pem" -CAkey "${WORKDIR}/intermediate/intermediate.key.pem" \
    -CAcreateserial -out "${OUTPUT}/server.crt.pem" -days 825 -sha384 \
    -extfile <(printf "subjectAltName=DNS:tcm.local,DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth")

# 4. Klienci  (zmiany: bez -clcerts, poprawne ścieżki tar)
for role in Operator Technik Serwis; do
  lower=$(echo "$role" | tr '[:upper:]' '[:lower:]')
  openssl genrsa -out "${WORKDIR}/clients/${lower}.key.pem" 4096
  openssl req -new -key "${WORKDIR}/clients/${lower}.key.pem" \
      -out "${WORKDIR}/clients/${lower}.csr.pem" \
      -subj "/C=PL/O=TCM Users/OU=${role}/CN=${role} Client"
  openssl x509 -req -in "${WORKDIR}/clients/${lower}.csr.pem" \
      -CA "${WORKDIR}/intermediate/intermediate.crt.pem" -CAkey "${WORKDIR}/intermediate/intermediate.key.pem" \
      -CAcreateserial -out "${WORKDIR}/clients/${lower}.crt.pem" -days 730 -sha384 \
      -extfile <(printf "extendedKeyUsage=clientAuth\nsubjectAltName=DNS:${lower}.local")
  cat "${WORKDIR}/clients/${lower}.crt.pem" "${OUTPUT}/ca-chain.crt" > "${WORKDIR}/clients/${lower}-fullchain.pem"
  openssl pkcs12 -export -in "${WORKDIR}/clients/${lower}-fullchain.pem" \
      -inkey "${WORKDIR}/clients/${lower}.key.pem" -out "${OUTPUT}/${lower}.p12" -passout pass:changeme
  tar -czf "${OUTPUT}/client-${lower}.tar.gz" \
      -C "${WORKDIR}/clients" "${lower}.key.pem" "${lower}-fullchain.pem" \
      -C "${OUTPUT}" "${lower}.p12"
  rm "${OUTPUT}/${lower}.p12"
done

# 5. CRL (nowa, kompletna konfiguracja dla openssl ca)
# wymagane pliki bazy CA
: > "${WORKDIR}/intermediate/index.txt"
echo 1000 > "${WORKDIR}/intermediate/serial"
echo 1000 > "${WORKDIR}/intermediate/crlnumber"

cat > "${WORKDIR}/intermediate/openssl.cnf" <<EOF
[ ca ]
default_ca = ca_intermediate

[ ca_intermediate ]
dir = ${WORKDIR}/intermediate
database = \$dir/index.txt
serial = \$dir/serial
crlnumber = \$dir/crlnumber
default_crl_days = 30
default_md = sha384
private_key = ${WORKDIR}/intermediate/intermediate.key.pem
certificate = ${WORKDIR}/intermediate/intermediate.crt.pem

[ policy_loose ]
commonName = supplied
EOF

openssl ca -gencrl -config "${WORKDIR}/intermediate/openssl.cnf" -out "${OUTPUT}/crl.pem"

