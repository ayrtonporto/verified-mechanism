# syntax=docker/dockerfile:1.7
# The runtime is intentionally self-contained: applicants never install Lean,
# Mathlib, REPL, or Comparator on the host.
FROM debian:bookworm-slim@sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241 AS builder

ARG TARGETARCH
ARG ELAN_COMMIT=b6cec7e10fe4965a605aaf60d1cb4a5837f0462b
ARG LEAN_VERSION=v4.32.0
ARG MATHLIB_COMMIT=81a5d257c8e410db227a6665ed08f64fea08e997
ARG REPL_COMMIT=68a3b3a059787a7db44fb1e6281e4a657efee470
ARG COMPARATOR_COMMIT=07bc4ea40f2266dcb861820a2ec1fa3244ed307f

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential zstd libgmp-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

ENV ELAN_HOME=/opt/elan
ENV PATH=/opt/elan/bin:${PATH}

RUN curl --fail --silent --show-error --location \
      "https://raw.githubusercontent.com/leanprover/elan/${ELAN_COMMIT}/elan-init.sh" \
      -o /tmp/elan-init.sh \
    && sh /tmp/elan-init.sh -y --default-toolchain none \
    && rm /tmp/elan-init.sh \
    && elan toolchain install "leanprover/lean4:${LEAN_VERSION}"

RUN git clone --filter=blob:none https://github.com/leanprover-community/mathlib4.git /opt/mathlib \
    && git -C /opt/mathlib checkout --detach "${MATHLIB_COMMIT}" \
    && cd /opt/mathlib \
    && lake exe cache get \
    && lake build \
    && lake env printenv > /opt/lean.env

RUN git clone --filter=blob:none https://github.com/leanprover-community/repl.git /opt/repl \
    && git -C /opt/repl checkout --detach "${REPL_COMMIT}" \
    && cd /opt/repl \
    && lake build repl

RUN git clone --filter=blob:none https://github.com/leanprover/comparator.git /opt/comparator \
    && git -C /opt/comparator checkout --detach "${COMPARATOR_COMMIT}" \
    && cd /opt/comparator \
    && lake build lean4export comparator

# Comparator needs a writable project build directory at runtime. Resolve its
# sole Mathlib path dependency now, while the image build has network access.
RUN mkdir -p /opt/project-template \
    && printf '%s\n' \
      'name = "TakehomeCheck"' \
      'version = "0.1.0"' \
      '' \
      '[[require]]' \
      'name = "mathlib"' \
      'path = "/opt/mathlib"' \
      '' \
      '[[lean_lib]]' \
      'name = "Challenge"' \
      '' \
      '[[lean_lib]]' \
      'name = "Solution"' \
      > /opt/project-template/lakefile.toml \
    && printf 'leanprover/lean4:%s\n' "${LEAN_VERSION}" > /opt/project-template/lean-toolchain \
    && mkdir -p /opt/project-template/.lake \
    && ln -s /opt/mathlib/.lake/packages /opt/project-template/.lake/packages \
    && cd /opt/project-template \
    && lake update \
    && rm -rf /opt/mathlib/.git /opt/repl/.git /opt/comparator/.git

RUN find /opt/elan /opt/mathlib /opt/repl /opt/comparator /opt/project-template \
      -type f ! -perm -004 -exec chmod go+r {} +

FROM debian:bookworm-slim@sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241 AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash git python3 ca-certificates libgmp10 libffi8 libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 65532 --no-create-home --shell /usr/sbin/nologin lean

COPY --from=builder /opt/elan /opt/elan
COPY --from=builder /opt/mathlib /opt/mathlib
COPY --from=builder /opt/repl /opt/repl
COPY --from=builder /opt/comparator /opt/comparator
COPY --from=builder /opt/project-template /opt/project-template
COPY --from=builder /opt/lean.env /opt/lean.env
COPY docker/entrypoint.py /opt/bin/entrypoint.py

ENV PATH=/opt/elan/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LEAN_VERSION=v4.32.0 \
    MATHLIB_COMMIT=81a5d257c8e410db227a6665ed08f64fea08e997 \
    REPL_COMMIT=68a3b3a059787a7db44fb1e6281e4a657efee470 \
    COMPARATOR_COMMIT=07bc4ea40f2266dcb861820a2ec1fa3244ed307f \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=safe.directory \
    GIT_CONFIG_VALUE_0=*

USER 65532:65532
WORKDIR /work
ENTRYPOINT ["python3", "/opt/bin/entrypoint.py"]
CMD ["health"]
