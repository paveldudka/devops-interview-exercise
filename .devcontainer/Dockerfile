FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ARG TERRAFORM_VERSION=1.9.8
ARG ACTIONLINT_VERSION=1.7.7
ARG TARGETARCH

RUN test -n "${TARGETARCH}" || { echo "TARGETARCH unset: build with BuildKit" >&2; exit 1; } \
    && case "${TARGETARCH}" in \
      amd64) terraform_sha="186e0145f5e5f2eb97cbd785bc78f21bae4ef15119349f6ad4fa535b83b10df8" ;; \
      arm64) terraform_sha="f85868798834558239f6148834884008f2722548f84034c9b0f62934b2d73ebb" ;; \
      *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl --fail --show-error --location --retry 3 \
      "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" \
      --output /tmp/terraform.zip \
    && echo "${terraform_sha}  /tmp/terraform.zip" | sha256sum --check \
    && unzip /tmp/terraform.zip -d /usr/local/bin \
    && rm /tmp/terraform.zip \
    && terraform version

RUN case "${TARGETARCH}" in \
      amd64) actionlint_sha="023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757" ;; \
      arm64) actionlint_sha="401942f9c24ed71e4fe71b76c7d638f66d8633575c4016efd2977ce7c28317d0" ;; \
      *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl --fail --show-error --location --retry 3 \
      "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_${TARGETARCH}.tar.gz" \
      --output /tmp/actionlint.tar.gz \
    && echo "${actionlint_sha}  /tmp/actionlint.tar.gz" | sha256sum --check \
    && tar -xzf /tmp/actionlint.tar.gz -C /usr/local/bin actionlint \
    && rm /tmp/actionlint.tar.gz \
    && actionlint -version
