#!/bin/bash
# find_special_text_token.sh
#
# text_emb has 32001 rows, text_linear only has 32000. That extra row (index 32000)
# in text_emb is almost certainly a reserved input-only special token (e.g. a
# start-of-text / initial token used internally by Moshi's generation loop).
#
# Before resizing anything, we need to know what that row means so our 15 new
# tokenizer tokens (currently assigned IDs 32000-32014 by add_tokens) don't
# collide with it.

echo "=== Searching moshi package source for special text token constants ==="
MOSHI_PKG=$(python3 -c "import moshi, os; print(os.path.dirname(moshi.__file__))")
echo "moshi package location: $MOSHI_PKG"
echo ""

echo "--- Grepping for '32000', '32001', 'text_pad', 'initial_token', 'start.*text', 'text.*start' ---"
grep -rn -iE "32000|32001|text_pad|initial_token|text.*start.*token|start.*text.*token" "$MOSHI_PKG" --include="*.py" | grep -v ".pyc"

echo ""
echo "--- Grepping for 'zero_token_id', 'text_card', 'text_vocab', 'vocab_size' near text ---"
grep -rn -iE "zero_token_id|text_card|text_vocab_size|n_q.*text|text.*n_q" "$MOSHI_PKG" --include="*.py" | grep -v ".pyc"

echo ""
echo "--- Checking moshi_lm's own attributes for anything vocab/token related ---"
python3 -c "
from huggingface_hub import hf_hub_download
from moshi.models import loaders as moshi_loaders

weight_path = hf_hub_download('kyutai/moshika-pytorch-bf16', filename='model.safetensors')
moshi_lm = moshi_loaders.get_moshi_lm(weight_path, device='cpu')

for attr in dir(moshi_lm):
    if attr.startswith('_'):
        continue
    if any(kw in attr.lower() for kw in ['text', 'vocab', 'card', 'pad', 'init', 'start', 'special']):
        try:
            val = getattr(moshi_lm, attr)
            if not callable(val):
                print(f'  {attr} = {val}')
        except Exception as e:
            print(f'  {attr} = <error: {e}>')
"
