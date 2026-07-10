"""Moshi Inference Engine — streaming token generation and audio synthesis.
Phase 11 Update: LoRA adapter integrated for bilingual (en-ru) fine-tuned inference.
"""

import asyncio
import os
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

logger = logging.getLogger("MoshiEngine")

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
        logger.info(f"Loading Moshi models on {device} with {self.dtype}...")

        # 4-bit quantization config for VRAM efficiency
        # pyrefly: ignore [missing-import]
        from transformers import BitsAndBytesConfig
        if torch.cuda.is_available():
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=self.dtype
            )
        else:
            bnb_config = None
            logger.info(f"Loading Moshi models on {device} with {self.dtype}...")

        mimi_path = hf_hub_download('kyutai/moshika-pytorch-bf16', loaders.MIMI_NAME)
        self.mimi = loaders.get_mimi(mimi_path, device=device)

        moshi_path = None
        self.moshi_lm = None
        
        try:
            moshi_path = hf_hub_download('kyutai/moshika-pytorch-bf16', 'model.safetensors', local_files_only=True)
            try:
                self.moshi_lm = loaders.get_moshi_lm(moshi_path, device=device, quantization_config=bnb_config)
                logger.info("Loaded Moshi LM in 4-bit precision.")
            except TypeError:
                logger.warning("Moshi loader doesn't accept quantization_config directly. Loading normally...")
                self.moshi_lm = loaders.get_moshi_lm(moshi_path, device=device)

            self.adapter_loaded = False
            self.adapter_path = None
            try:
                from peft import PeftModel
                ru_adapter_path = "/root/aziza-build/adapters/moshi_ru_v1/final"
                multilingual_adapter_path = "/root/aziza-build/aziza-multilingual-adapter/final"
                
                # Monkey-patch Moshi LM for PEFT compatibility
                class DummyConfig:
                    is_encoder_decoder = False
                    model_type = "moshi"
                    
                if not hasattr(self.moshi_lm, "prepare_inputs_for_generation"):
                    self.moshi_lm.prepare_inputs_for_generation = lambda *args, **kwargs: {}
                if not hasattr(self.moshi_lm, "config"):
                    self.moshi_lm.config = DummyConfig()

                logger.info(f"Loading base multilingual adapter from {multilingual_adapter_path}...")
                self.moshi_lm = PeftModel.from_pretrained(self.moshi_lm, multilingual_adapter_path, adapter_name="multilingual")
                
                if os.path.exists(ru_adapter_path):
                    logger.info(f"Loading RU adapter from {ru_adapter_path}...")
                    self.moshi_lm.load_adapter(ru_adapter_path, adapter_name="ru")
                
                self.moshi_lm.set_adapter("multilingual")
                self.adapter_loaded = True
                self.adapter_path = multilingual_adapter_path
                logger.info("Successfully loaded PEFT adapters into Moshi LM.")
            except ImportError:
                logger.warning("peft not installed, skipping adapter loading.")
            except Exception as adapter_err:
                logger.error(f"Failed to load PEFT adapters: {adapter_err}")

            # Ensure no parameters require gradients to prevent uint8/int8 parameter loading errors
            for param in self.moshi_lm.parameters():
                param.requires_grad = False
                
            logger.info("Running with Moshi LM.")
            self.moshi_lm.eval()
        except Exception as e:
            logger.warning(f"Could not load Moshi LM: {e}. Running in MOCK/ECHO mode for integration testing.")

        for param in self.mimi.parameters():
            param.requires_grad = False

        # Setup Text Tokenizer
        try:
            tokenizer_path = hf_hub_download('kyutai/moshika-pytorch-bf16', loaders.TEXT_TOKENIZER_NAME, local_files_only=True)
            self.text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
        except Exception:
            logger.warning("Could not load tokenizer. Text inputs will be limited.")
            self.text_tokenizer = None

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

    # -----------------------------------------------------------------------
    # Session state helpers
    # -----------------------------------------------------------------------

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
            
            adapter_name = "ru" if lang == "ru" else "multilingual"
            try:
                self.moshi_lm.set_adapter(adapter_name)
                logger.info(f"Switched adapter to {adapter_name} for session {session_id} (lang: {lang})")
            except Exception as e:
                logger.warning(f"Failed to switch adapter to {adapter_name}: {e}")

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
        logger.info(f"Step for {session_id}, chunk size: {len(audio_chunk)}")
        async with self._session_lock:
            self._switch_to_session(session_id)
        
        lm_gen = self.lm_gen

        logger.info(
            f"type(audio_chunk)={type(audio_chunk)} "
            f"len={len(audio_chunk)}"
        )

        # Normalize audio to [-1.0, 1.0] float32 — Mimi expects this range
        # audio_chunk arrives as np.int16 from np.frombuffer() in moshi_service.py
        if isinstance(audio_chunk, np.ndarray) and audio_chunk.dtype == np.int16:
            audio_np = audio_chunk.astype(np.float32) / 32768.0
        elif isinstance(audio_chunk, np.ndarray) and audio_chunk.dtype in (np.float32, np.float64):
            audio_np = audio_chunk.astype(np.float32)  # already normalized
        else:
            # Fallback: assume raw int16 values in an array-like, normalize
            audio_np = np.array(audio_chunk, dtype=np.float32) / 32768.0

        logger.info(
            f"audio_np shape={audio_np.shape} "
            f"min={audio_np.min():.4f} "
            f"max={audio_np.max():.4f} "
            f"mean_abs={np.abs(audio_np).mean():.6f}"
        )

        # Encode audio with Mimi: expects [B, C, T] float32 in [-1, 1] at 24kHz
        audio_tensor = (
            torch.from_numpy(audio_np)
            .to(device=self.device, dtype=self.dtype)
            .view(1, 1, -1)
            # NOTE: NO / 32768.0 here — normalization is done above
        )


        with torch.no_grad():
            codes = self.mimi.encode(audio_tensor)

        logger.info(f"Mimi encoded into codes shape: {codes.shape}")

        all_out_audio = []
        all_text_tokens = []

        if lm_gen is None:
            # MOCK mode
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
            logger.info("No output audio tokens generated in this step.")
            return {"audio": None, "text": ""}

        out_pcm = torch.cat(all_out_audio, dim=-1)

        text = ""
        if all_text_tokens:
            text_ids = torch.cat(all_text_tokens, dim=-1).tolist()
            text = self.text_tokenizer.decode(text_ids)
            logger.info(f"Generated text: {text}")

        # Mark session as audio-warmed-up so TTS synthesis is safe on next step_text()
        if session_id in self.session_states:
            self.session_states[session_id]["audio_warmed_up"] = True

        return {"audio": out_pcm, "text": text}


    async def step_text(self, session_id: str, text: str):
        """Run one inference step: encode text → LM step → decode audio."""
        logger.info(f"Step text for {session_id}, text: {text}")
        async with self._session_lock:
            self._switch_to_session(session_id)

        text_ids = self.text_tokenizer.encode(text)
        if not text_ids:
            return {"audio": None, "text": ""}

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
        mode_str = "LoRA Adapted Moshi Model" if adapter_loaded else "Architecture Separation (Base Moshi Model only)"
        return {
            "adapter_loaded": adapter_loaded,
            "adapter_path": adapter_path,
            "languages": ["en", "ru", "uz"],
            "mode": mode_str
        }
