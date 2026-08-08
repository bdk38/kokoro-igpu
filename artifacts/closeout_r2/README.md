# Close-out R2 smoke (2026-08-08)

Final same-host product-path rehearsal before board close (notes/77).  
Not a stranger clone — R0/R1 already tagged that.

| Tree | Legs | Result |
|------|------|--------|
| monorepo smoke_product.sh :8899 | ort-cpu, ov-gpu, ovgenai-gpu | PASS |
| genai smoke.sh :8890 | ovgenai-cpu, ovgenai-gpu | PASS |

WAVs under `poc/` and `genai/`. Daily `:8880` remained ort-cpu PoC face.
