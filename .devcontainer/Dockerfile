FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ARG TERRAFORM_VERSION=1.9.8
ARG ACTIONLINT_VERSION=1.7.7
ARG TARGETARCH=amd64

RUN curl --fail --show-error --location --retry 3 \
      "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" \
      --output /tmp/terraform.zip \
    && unzip /tmp/terraform.zip -d /usr/local/bin \
    && rm /tmp/terraform.zip \
    && terraform version

RUN curl --fail --show-error --location --retry 3 \
      "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_${TARGETARCH}.tar.gz" \
      --output /tmp/actionlint.tar.gz \
    && tar -xzf /tmp/actionlint.tar.gz -C /usr/local/bin actionlint \
    && rm /tmp/actionlint.tar.gz \
    && actionlint -version
