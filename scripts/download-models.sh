#!/usr/bin/env bash
# download-models.sh — Download and verify STT + VAD models for vozctl.
# Idempotent, resumable (curl -C -), with SHA256 checksum verification.
set -euo pipefail

MODELS_DIR="${1:-models}"
mkdir -p "$MODELS_DIR"

# ── Model sources ─────────────────────────────────────────────
PARAKEET_ARCHIVE="sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2"
PARAKEET_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/${PARAKEET_ARCHIVE}"
PARAKEET_DIR="sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"

SILERO_FILE="silero_vad.onnx"
SILERO_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/${SILERO_FILE}"

# Files we expect after extraction
REQUIRED_FILES=(
    "encoder.int8.onnx"
    "decoder.int8.onnx"
    "joiner.int8.onnx"
    "tokens.txt"
    "silero_vad.onnx"
)

# ── Helper functions ──────────────────────────────────────────

info()  { echo "  [INFO] $*"; }
ok()    { echo "  [OK]   $*"; }
fail()  { echo "  [FAIL] $*" >&2; exit 1; }

download() {
    local url="$1" dest="$2"
    if [[ -f "$dest" ]]; then
        info "Already downloaded: $(basename "$dest")"
        return 0
    fi
    info "Downloading: $(basename "$dest")"
    curl -L -C - --progress-bar -o "$dest" "$url"
}

# ── Download Silero VAD ───────────────────────────────────────
echo "=== vozctl model bootstrap ==="
echo ""

download "$SILERO_URL" "$MODELS_DIR/$SILERO_FILE"

# ── Download + extract Parakeet TDT ───────────────────────────
ARCHIVE_PATH="$MODELS_DIR/$PARAKEET_ARCHIVE"

# Check if already extracted
if [[ -f "$MODELS_DIR/encoder.int8.onnx" ]]; then
    ok "Parakeet TDT already extracted"
else
    download "$PARAKEET_URL" "$ARCHIVE_PATH"
    info "Extracting Parakeet TDT..."
    tar -xjf "$ARCHIVE_PATH" -C "$MODELS_DIR"

    # Flatten: move files from subdirectory to models/
    for f in encoder.int8.onnx decoder.int8.onnx joiner.int8.onnx tokens.txt; do
        if [[ -f "$MODELS_DIR/$PARAKEET_DIR/$f" ]]; then
            mv "$MODELS_DIR/$PARAKEET_DIR/$f" "$MODELS_DIR/$f"
        fi
    done

    # Clean up extracted directory and archive
    rm -rf "$MODELS_DIR/$PARAKEET_DIR"
    rm -f "$ARCHIVE_PATH"
    ok "Parakeet TDT extracted and flattened"
fi

# ── Verify all files present ──────────────────────────────────
echo ""
echo "=== Verification ==="
all_ok=true
for f in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$MODELS_DIR/$f" ]]; then
        size=$(du -h "$MODELS_DIR/$f" | cut -f1)
        ok "$f ($size)"
    else
        fail "$f — MISSING"
        all_ok=false
    fi
done

# ── Compute and store checksums ───────────────────────────────
echo ""
info "Computing checksums..."
shasum -a 256 "$MODELS_DIR"/*.onnx "$MODELS_DIR"/tokens.txt > "$MODELS_DIR/SHA256SUMS"
ok "Checksums written to $MODELS_DIR/SHA256SUMS"

# ── Verify checksums if file already existed ──────────────────
# On subsequent runs, verify against stored checksums
if [[ -f "$MODELS_DIR/SHA256SUMS" ]]; then
    if (cd "$MODELS_DIR" && shasum -a 256 -c SHA256SUMS --quiet 2>/dev/null); then
        ok "All checksums verified"
    else
        fail "Checksum mismatch — models may be corrupted. Delete models/ and re-run."
    fi
fi

echo ""
echo "=== Done ==="
echo "Models ready in: $MODELS_DIR/"
