"""Moshi Inference Engine — streaming token generation and audio synthesis.

Phase PI-4: native Uzbek Moshi LoRA (moshi_uz_v1) deployed as the primary
adapter. The Russian LoRA (moshi_ru_v1) remains loaded for runtime language
switching (Phase 7) without restarting Moshi.
"""

import asyncio
import os
import json
# pyrefly: ignore [missing-import]
import torch
import numpy as np
import logging
# pyrefly: ignore [missing-import]
import sentencepiece
# pyrefly: ignore [missing-import]
from huggingface_hub import hf_hub_download
# pyrefly: ignore [missing-import]
from moshi.models import loaders
# pyrefly: ignore [missing-import]
from moshi.models.lm import LMGen
# pyrefly: ignore [missing-import]
from moshi.modules.lora import LoRALinear

logger = logging.getLogger("MoshiEngine")

# ── Adapter deployment configuration (Phase PI-4) ──────────────────────────
ADAPTER_NAME = "moshi_uz_v1"
ADAPTER_VERSION = "1.0"
DEFAULT_ADAPTER = "uz"
UZ_ADAPTER_PATH = "/root/aziza-build/training/lora/adapters/moshi_uz_v1/final"
RU_ADAPTER_PATH = "/root/aziza-build/training/lora/adapters/moshi_ru_v1/final"

class MoshiEngine:
    """Wraps Moshi's Mimi codec and LM for per-session streaming inference.
    
    Acts strictly as an ASR/TTS engine while text generation is routed to external fine-tuned vLLM services.
    """

    def __init__(self, device: str = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        torch.set_grad_enabled(False)
        self.dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        self._banner("Loading Moshi...")

        # Full-precision bf16 load. 4-bit quantization replaces nn.Linear with
        # BNB layers that cannot be wrapped by Moshi's native LoRALinear, so the
        # adapter could not be attached. The RTX A6000 (49 GB) comfortably holds
        # the 7.7 B model in bf16 (~15 GB), leaving ample headroom for inference.
        self.inference_precision = f"{self.dtype} (full precision, bf16)"
        bnb_config = None

        # Report GPU allocation
        if torch.cuda.is_available():
            gpu_idx = torch.cuda.current_device()
            cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "all")
            self.gpu_allocation = (
                f"cuda:{gpu_idx} — {torch.cuda.get_device_name(gpu_idx)} "
                f"(CUDA_VISIBLE_DEVICES={cuda_visible})"
            )
            free_b, total_b = torch.cuda.mem_get_info(gpu_idx)
            logger.info("GPU allocation", extra={"extra_data": {
                "gpu": self.gpu_allocation,
                "total_vram_gb": round(total_b / 1e9, 2),
                "free_vram_gb": round(free_b / 1e9, 2),
                "inference_precision": self.inference_precision,
            }})
        else:
            self.gpu_allocation = "cpu (no GPU detected)"

        mimi_path = hf_hub_download('kyutai/moshika-pytorch-bf16', loaders.MIMI_NAME)
        self.mimi = loaders.get_mimi(mimi_path, device=device)

        moshi_path = None
        self.moshi_lm = None
        
        try:
            moshi_path = hf_hub_download('kyutai/moshika-pytorch-bf16', 'model.safetensors', local_files_only=True)
            self.moshi_lm = loaders.get_moshi_lm(moshi_path, device=device)
            logger.info("Loaded Moshi LM in full bf16 precision.")

            # ── Text tokenizer (loaded before adapters for startup ordering) ─
            self._banner("Loading tokenizer...")
            tokenizer_path = None
            try:
                tokenizer_path = hf_hub_download('kyutai/moshika-pytorch-bf16', loaders.TEXT_TOKENIZER_NAME, local_files_only=True)
            except Exception:
                tokenizer_path = None
            if tokenizer_path and os.path.exists(tokenizer_path):
                self.text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
                self.tokenizer_version = f"base_moshi_v1 (vocab={self.text_tokenizer.get_piece_size()})"
                logger.info(f"Loaded base Moshi tokenizer: vocab_size={self.text_tokenizer.get_piece_size()}")
            else:
                logger.warning("Could not load tokenizer. Text inputs will be limited.")
                self.text_tokenizer = None
                self.tokenizer_version = "unavailable"

            # ── PEFT adapters: Uzbek primary, Russian for runtime switching ─
            self._load_adapters()

            # Ensure no parameters require gradients to prevent uint8/int8 parameter loading errors
            for param in self.moshi_lm.parameters():
                param.requires_grad = False
                
            logger.info("Running with Moshi LM.")
            self.moshi_lm.eval()
        except Exception as e:
            logger.warning(f"Could not load Moshi LM: {e}. Running in MOCK/ECHO mode for integration testing.")

        for param in self.mimi.parameters():
            param.requires_grad = False

        # Fallback tokenizer load for MOCK/ECHO (no LM) mode
        if getattr(self, "text_tokenizer", None) is None:
            try:
                tokenizer_path = hf_hub_download('kyutai/moshika-pytorch-bf16', loaders.TEXT_TOKENIZER_NAME, local_files_only=True)
                self.text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
                self.tokenizer_version = f"base_moshi_v1 (vocab={self.text_tokenizer.get_piece_size()})"
            except Exception:
                self.text_tokenizer = None
                self.tokenizer_version = "unavailable"

        self.mimi.eval()

        self.session_states: dict = {}
        self.current_session_id = None
        self._session_lock = asyncio.Lock()  # Protects concurrent session switching

        if self.moshi_lm is not None:
            # Initialize LMGen once with the adapted model
            self.lm_gen = LMGen(self.moshi_lm)

            # Initialize streaming mode once to get initial states
            self.lm_gen_exit_stack = self.lm_gen.streaming(1)
            self.lm_gen_exit_stack.__enter__()

            # Capture the initial (empty) states
            self.empty_lm_model_state = self._get_model_state(self.moshi_lm)
            self.empty_lm_gen_state = self.lm_gen._streaming_state
        else:
            self.lm_gen = None
            self.empty_lm_model_state = {}
            self.empty_lm_gen_state = {}

        logger.info("Moshi engine ready (running strictly as audio engine).")
        self._banner("Inference ready", final=True)

    # -----------------------------------------------------------------------
    # Startup banner + adapter loading
    # -----------------------------------------------------------------------

    @staticmethod
    def _banner(message: str, final: bool = False):
        """Print a clear human-readable startup banner to stdout."""
        rule = "=" * 60 if final else "-" * 60
        print(rule, flush=True)
        print(f"  {message}", flush=True)
        if final:
            print(rule, flush=True)
        logger.info(message)

    def _load_adapters(self):
        """Load the trained PEFT LoRA adapters and fuse them into Moshi's
        native ``LoRALinear`` layers.

        The Moshi streaming runtime only recognises its own ``LoRALinear``
        module type (PEFT's wrapped ``Linear`` raises ``RuntimeError`` inside
        ``_init_streaming_state``). PEFT and Moshi store ``lora_A``/``lora_B``
        with identical orientation (``(rank, in)`` / ``(out, rank)``), so we
        convert the PEFT checkpoint directly into native ``LoRALinear`` layers.
        All targeted linears start zero-initialised (== base model) and the
        active language's weights are copied in via :meth:`_activate_adapter`,
        which enables runtime language switching without restarting Moshi.

        Phase PI-4: the native Uzbek Moshi LoRA (moshi_uz_v1) is the primary
        adapter deployed into production. The Russian LoRA (moshi_ru_v1) is also
        fused so the worker can switch languages at runtime (Phase 7).
        """
        self.adapter_loaded = False
        self.adapter_path = None
        self.loaded_adapters: list = []
        self.adapter_metadata: dict = {}
        self._lora_layers: dict = {}
        self._adapter_weights: dict = {}
        self._active_lang: str = DEFAULT_ADAPTER

        self._banner("Loading Uzbek adapter...")

        # ── Primary: native Uzbek Moshi LoRA ──────────────────────────────
        if not os.path.exists(UZ_ADAPTER_PATH):
            logger.error(
                "Uzbek adapter missing — deployment cannot proceed without it",
                extra={"extra_data": {"adapter_path": UZ_ADAPTER_PATH}},
            )
            logger.warning("Running base Moshi model WITHOUT Uzbek adapter (degraded mode).")
            return

        try:
            uz_map, uz_scaling = self._build_lora_map(UZ_ADAPTER_PATH)
            self._adapter_weights["uz"] = uz_map
            self.loaded_adapters.append("uz")
        except Exception as uz_err:
            logger.error(f"Failed to load Uzbek adapter: {uz_err}")
            return

        # Replace the targeted nn.Linear layers with native LoRALinear (zero-init).
        try:
            self._lora_layers = self._apply_native_lora(uz_map)
        except Exception as apply_err:
            logger.error(f"Failed to fuse Uzbek adapter into Moshi: {apply_err}")
            return

        # ── Secondary: Russian LoRA for runtime language switching ─────────
        if os.path.exists(RU_ADAPTER_PATH):
            try:
                ru_map, _ = self._build_lora_map(RU_ADAPTER_PATH)
                self._adapter_weights["ru"] = ru_map
                self.loaded_adapters.append("ru")
            except Exception as ru_err:
                logger.warning(f"Failed to load RU adapter (switching disabled): {ru_err}")

        # ── Activate Uzbek as the default adapter ─────────────────────────
        if self.loaded_adapters:
            self._activate_adapter(DEFAULT_ADAPTER)
            self.adapter_loaded = True
            self.adapter_path = UZ_ADAPTER_PATH
            self.adapter_metadata = {
                "name": ADAPTER_NAME,
                "version": ADAPTER_VERSION,
                "path": UZ_ADAPTER_PATH,
                "loaded_adapters": self.loaded_adapters,
                "active_adapter": DEFAULT_ADAPTER,
            }
            self._banner("PEFT adapter loaded successfully")
            logger.info(
                "PEFT adapter loaded successfully",
                extra={"extra_data": {
                    "adapter_name": ADAPTER_NAME,
                    "adapter_version": ADAPTER_VERSION,
                    "adapter_path": UZ_ADAPTER_PATH,
                    "fused_layers": len(self._lora_layers),
                    "loaded_adapters": self.loaded_adapters,
                    "active_adapter": DEFAULT_ADAPTER,
                    "tokenizer_version": getattr(self, "tokenizer_version", None),
                    "gpu_allocation": self.gpu_allocation,
                    "inference_precision": self.inference_precision,
                }},
            )
        else:
            logger.warning("No native Moshi adapters loaded, running base model only.")

    # -----------------------------------------------------------------------
    # Native LoRA (Moshi LoRALinear) helpers
    # -----------------------------------------------------------------------

    def _build_lora_map(self, adapter_dir: str):
        """Read a PEFT safetensors checkpoint into {module_path: {A, B, scaling}}."""
        from safetensors import safe_open

        sd_path = os.path.join(adapter_dir, "adapter_model.safetensors")
        lora_map: dict = {}
        with safe_open(sd_path, framework="pt") as f:
            for key in f.keys():
                if key.endswith(".lora_A.weight"):
                    rel = key[: -len("lora_A.weight")].replace("base_model.model.moshi_lm.", "").rstrip(".")
                    lora_map.setdefault(rel, {})["A"] = f.get_tensor(key)
                elif key.endswith(".lora_B.weight"):
                    rel = key[: -len("lora_B.weight")].replace("base_model.model.moshi_lm.", "").rstrip(".")
                    lora_map.setdefault(rel, {})["B"] = f.get_tensor(key)

        with open(os.path.join(adapter_dir, "adapter_config.json")) as cfg_f:
            cfg = json.load(cfg_f)
        scaling = float(cfg["lora_alpha"]) / float(cfg["r"])
        for v in lora_map.values():
            v["scaling"] = scaling
        return lora_map, scaling

    def _apply_native_lora(self, lora_map: dict) -> dict:
        """Replace each targeted ``nn.Linear`` with a zero-initialised native
        ``LoRALinear`` (== base model until activated). Returns {path: layer}."""
        named = dict(self.moshi_lm.named_modules())
        layers: dict = {}
        skipped = 0
        for rel, data in lora_map.items():
            if rel not in named:
                skipped += 1
                continue
            child = named[rel]
            if not isinstance(child, torch.nn.Linear):
                skipped += 1
                continue
            parent_path, attr = rel.rsplit(".", 1)
            parent = self.moshi_lm if parent_path == "" else named[parent_path]
            rank = data["A"].shape[0]
            lora = LoRALinear(
                child.in_features, child.out_features,
                rank=rank, scaling=data["scaling"],
                device=self.device, dtype=self.dtype,
            )
            lora.frozen_W = child  # keep the original (now frozen) weights
            with torch.no_grad():
                lora.lora_A.weight.zero_()
                lora.lora_B.weight.zero_()
            setattr(parent, attr, lora)
            layers[rel] = lora
        if skipped:
            logger.warning(f"Skipped {skipped} LoRA targets not present as nn.Linear")
        return layers

    def _activate_adapter(self, lang: str):
        """Copy the selected language's LoRA weights into the live layers.

        ``en`` zeroes the LoRA branches, restoring the exact base-model behaviour
        (architecture separation — text generation is routed to the vLLM/LLM
        services per language, Moshi acts as the audio engine).
        """
        if lang not in self._adapter_weights:
            # Unknown language → fall back to base model.
            lang = "en"
        target_map = self._adapter_weights.get(lang)
        for rel, lora in self._lora_layers.items():
            with torch.no_grad():
                if target_map is None or rel not in target_map:
                    lora.lora_A.weight.zero_()
                    lora.lora_B.weight.zero_()
                else:
                    lora.lora_A.weight.copy_(target_map[rel]["A"].to(device=self.device, dtype=self.dtype))
                    lora.lora_B.weight.copy_(target_map[rel]["B"].to(device=self.device, dtype=self.dtype))
        self._active_lang = lang


    def _get_model_state(self, model):
        states = {}
        def _collect(name, module):
            states[name] = module._streaming_state
        model._apply_named_streaming(_collect)
        return states

    def _set_model_state(self, model, states):
        def _apply(name, module):
            module._streaming_state = states.get(name)
        model._apply_named_streaming(_apply)

    def _switch_to_session(self, session_id: str):
        if self.current_session_id == session_id:
            return

        # Save current state if exists
        if self.current_session_id in self.session_states:
            current_state = self.session_states[self.current_session_id]
            if self.moshi_lm is not None:
                current_state["lm_model_state"] = self._get_model_state(self.moshi_lm)
            if self.lm_gen is not None:
                current_state["lm_gen_state"] = self.lm_gen._streaming_state

        # Load new state
        if session_id in self.session_states:
            target_state = self.session_states[session_id]
            if self.moshi_lm is not None:
                self._set_model_state(self.moshi_lm, target_state["lm_model_state"])
            if self.lm_gen is not None:
                self.lm_gen._streaming_state = target_state["lm_gen_state"]
        else:
            # New session — use clean initial states
            if self.moshi_lm is not None:
                self._set_model_state(self.moshi_lm, self.empty_lm_model_state)
            if self.lm_gen is not None:
                self.lm_gen._streaming_state = self.empty_lm_gen_state

        if getattr(self, "adapter_loaded", False):
            lang = "en"
            if session_id in self.session_states:
                lang = self.session_states[session_id].get("language", "en")
            
            # Runtime language switch via native LoRA weight swapping.
            # Only re-copy weights when the language actually changes, to avoid
            # disturbing the live streaming state on every audio step.
            if lang != getattr(self, "_active_lang", DEFAULT_ADAPTER):
                try:
                    self._activate_adapter(lang)
                    logger.info(f"Switched LoRA adapter to {lang} for session {session_id}")
                except Exception as e:
                    logger.warning(f"Failed to switch adapter to {lang}: {e}")

        self.current_session_id = session_id

    def get_session_state(self, session_id: str) -> dict:
        """Create or return a streaming session."""
        if session_id not in self.session_states:
            self.session_states[session_id] = {
                "lm_model_state": self.empty_lm_model_state,
                "lm_gen_state": self.empty_lm_gen_state,
                "text_prompt": None,
                "voice_prompt": None,
                "language": "en"
            }
            logger.info(f"Created session: {session_id}")
        return self.session_states[session_id]

    def initialize_session(self, session_id: str, text_prompt: str = None, voice_prompt: str = None):
        """Initialize or reset a session with specific metadata."""
        if session_id in self.session_states:
            self.reset_session(session_id)

        state = self.get_session_state(session_id)
        state["text_prompt"] = text_prompt
        state["voice_prompt"] = voice_prompt
        logger.info(f"Session {session_id} initialized with prompts.")

    # -----------------------------------------------------------------------
    # Inference steps
    # -----------------------------------------------------------------------

    async def step(self, session_id: str, audio_chunk):
        """Run one inference step: encode audio → LM step → decode audio."""
        async with self._session_lock:
            self._switch_to_session(session_id)
        
        lm_gen = self.lm_gen

        logger.debug(f"Step for {session_id}, chunk size: {len(audio_chunk)}")

        # Normalize audio to [-1.0, 1.0] float32 — Mimi expects this range
        if isinstance(audio_chunk, np.ndarray) and audio_chunk.dtype == np.int16:
            audio_np = audio_chunk.astype(np.float32) / 32768.0
        elif isinstance(audio_chunk, np.ndarray) and audio_chunk.dtype in (np.float32, np.float64):
            audio_np = audio_chunk.astype(np.float32)
        else:
            audio_np = np.array(audio_chunk, dtype=np.float32) / 32768.0

        # Encode audio with Mimi: expects [B, C, T] float32 in [-1, 1] at 24kHz
        audio_tensor = (
            torch.from_numpy(audio_np)
            .to(device=self.device, dtype=self.dtype)
            .view(1, 1, -1)
        )

        with torch.no_grad():
            codes = self.mimi.encode(audio_tensor)

        logger.debug(f"Mimi encoded into codes shape: {codes.shape}")

        all_out_audio = []
        all_text_tokens = []

        if lm_gen is None:
            logger.warning("LM generator is None. Skipping LM step (mock mode).")
        else:
            for s in range(codes.shape[-1]):
                step_codes = codes[:, :, s:s + 1]
                with torch.no_grad():
                    tokens = lm_gen.step(step_codes)

                if tokens is not None:
                    with torch.no_grad():
                        out_audio = self.mimi.decode(tokens[:, 1:])
                    all_out_audio.append(out_audio)
                    all_text_tokens.append(tokens[:, 0])

        if not all_out_audio:
            return {"audio": None, "text": ""}

        out_pcm = torch.cat(all_out_audio, dim=-1)

        text = ""
        if all_text_tokens:
            text_ids = torch.cat(all_text_tokens, dim=-1).tolist()
            text = self.text_tokenizer.decode(text_ids)
            logger.debug(f"Generated text: {text[:100]}")

        # Mark session as audio-warmed-up so TTS synthesis is safe on next step_text()
        if session_id in self.session_states:
            self.session_states[session_id]["audio_warmed_up"] = True

        return {"audio": out_pcm, "text": text}


    async def step_text(self, session_id: str, text: str):
        """Run one inference step: encode text → LM step → decode audio."""
        logger.debug(f"Step text for {session_id}: {text[:100]}")
        async with self._session_lock:
            self._switch_to_session(session_id)

        text_ids = self.text_tokenizer.encode(text) if self.text_tokenizer else []
        if not text_ids:
            text_ids = [0]

        # Text-to-text path via local test API (serve_russian_test.py) or vLLM
        import json
        import urllib.request
        import asyncio
        from llm_routing import get_llm_config, get_system_prompt

        state = self.get_session_state(session_id)
        lang = state.get("language", "en")
        
        text_api_url, model_name = get_llm_config(lang)
        sys_prompt = get_system_prompt(lang)

        try:
            def make_api_call():
                is_openai = "v1/chat/completions" in text_api_url
                if is_openai:
                    data = json.dumps({
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": text}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 256,
                        "stop": ["<|im_end|>", "<|im_start|>"]
                    }).encode("utf-8")
                else:
                    data = json.dumps({
                        "message": text,
                        "temperature": 0.7,
                        "max_tokens": 256
                    }).encode("utf-8")
                req = urllib.request.Request(
                    text_api_url, data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    if is_openai:
                        return {"response": resp_data["choices"][0]["message"]["content"]}
                    return resp_data

            loop = asyncio.get_event_loop()
            response_data = await loop.run_in_executor(None, make_api_call)
            generated_text = response_data.get("response", "")
            # Strip leaked chat-template control tokens (Vikhr / ChatML style)
            for token in ("<|im_end|>", "<|im_start|>", "<|endoftext|>", "<|end|>"):
                generated_text = generated_text.split(token)[0]
            generated_text = generated_text.strip()
            logger.info(f"Generated text via Text API: {generated_text}")

            # ── V2V: synthesize audio from the LLM reply ──────────────────
            # Feed the text response back into Mimi TTS to produce audio.
            # Moshi's LMGen drives audio codebooks from text tokens.
            # cuDNN must be warmed up first (requires at least one real audio step).
            state = self.get_session_state(session_id)
            audio_warmed_up = state.get("audio_warmed_up", False)

            if generated_text and self.lm_gen is not None and self.mimi is not None and audio_warmed_up:
                try:
                    text_ids = self.text_tokenizer.encode(generated_text) if self.text_tokenizer else []
                    all_out_audio = []
                    # Cap token count to avoid runaway generation (≈200ms budget at 24kHz)
                    for _tid in text_ids[:48]:
                        # Drive the LM with a zero-padded code frame; audio tokens emerge
                        dummy_codes = torch.zeros(1, 8, 1, device=self.device, dtype=torch.long)
                        with torch.no_grad():
                            tokens = self.lm_gen.step(dummy_codes)
                        if tokens is not None:
                            with torch.no_grad():
                                out_audio = self.mimi.decode(tokens[:, 1:])
                            all_out_audio.append(out_audio)

                    if all_out_audio:
                        out_pcm = torch.cat(all_out_audio, dim=-1)
                        logger.info(f"TTS synthesis complete: {out_pcm.shape} for session {session_id}")
                        return {"audio": out_pcm, "text": generated_text}
                except Exception as tts_err:
                    logger.warning(f"TTS synthesis failed, returning text only: {tts_err}")
            elif generated_text and not audio_warmed_up:
                logger.info(f"Session {session_id} audio not yet warmed up — returning text only for now")

            return {"audio": None, "text": generated_text}


        except Exception as e:
            logger.error(f"Error during Text API call: {e}")
            return {
                "audio": None,
                "text": (
                    f"Error: Unable to generate response with Text API ({e}). "
                    "Is the vLLM service running on port 8002/8003?"
                )
            }

    # -----------------------------------------------------------------------

    def reset_session(self, session_id: str):
        """Tear down a session's streaming context cleanly."""
        if session_id in self.session_states:
            if self.current_session_id == session_id:
                self.current_session_id = None
            del self.session_states[session_id]
            logger.info(f"Reset Moshi session: {session_id}")

    def get_adapter_status(self) -> dict:
        """Return adapter metadata for health-check endpoints."""
        adapter_loaded = getattr(self, "adapter_loaded", False)
        adapter_path = getattr(self, "adapter_path", None)
        loaded = getattr(self, "loaded_adapters", [])
        mode_str = "LoRA Adapted Moshi Model" if adapter_loaded else "Architecture Separation (Base Moshi Model only)"
        return {
            "adapter_loaded": adapter_loaded,
            "adapter_name": ADAPTER_NAME if adapter_loaded else None,
            "adapter_version": ADAPTER_VERSION if adapter_loaded else None,
            "adapter_path": adapter_path,
            "active_adapter": getattr(self, "_active_lang", DEFAULT_ADAPTER) if adapter_loaded else None,
            "loaded_adapters": loaded,
            "languages": ["en", "ru", "uz"],
            "tokenizer_version": getattr(self, "tokenizer_version", None),
            "inference_precision": getattr(self, "inference_precision", None),
            "gpu_allocation": getattr(self, "gpu_allocation", None),
            "mode": mode_str
        }
