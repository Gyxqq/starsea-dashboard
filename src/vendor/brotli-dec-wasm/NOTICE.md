# brotli-dec-wasm

Vendored browser Brotli decompressor used by the dashboard to read the
compressed save payload (`storage.algorithm = brotli-q4-v1`) directly in the
browser.

- Package: `brotli-dec-wasm`
- Version: 2.3.2
- Source: https://www.npmjs.com/package/brotli-dec-wasm
- Upstream: https://github.com/ustclug-dev/brotli-dec-wasm
- License: MIT OR Apache-2.0 (see LICENSE-MIT.txt / LICENSE-APACHE.txt)

Files:

- `brotli_dec_wasm.js` — wasm-bindgen ESM glue (`decompress`, `default init`)
- `brotli_dec_wasm_bg.wasm` — Brotli decompressor compiled to WebAssembly
