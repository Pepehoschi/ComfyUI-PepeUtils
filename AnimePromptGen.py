import os
from functools import lru_cache

import folder_paths
import torch


GGUF_FOLDERS = (
    ("gguf", "gguf"),
    ("llm_gguf", "llm_gguf"),
    ("LLM_GGUF", os.path.join("LLM", "GGUF")),
)
GGUF_NONE = "none"
DEFAULT_MODEL_ID = "FredZhang7/anime-anything-promptgen-v2"
DEFAULT_TOKENIZER_ID = "distilgpt2"


def _register_gguf_folder():
    if not hasattr(folder_paths, "models_dir") or not hasattr(folder_paths, "add_model_folder_path"):
        return

    for folder_key, folder_name in GGUF_FOLDERS:
        gguf_dir = os.path.join(folder_paths.models_dir, folder_name)
        folder_paths.add_model_folder_path(folder_key, gguf_dir)


def _gguf_files():
    if not hasattr(folder_paths, "get_filename_list"):
        return []

    files = []
    for folder_key, _folder_name in GGUF_FOLDERS:
        try:
            for name in folder_paths.get_filename_list(folder_key):
                if name.lower().endswith(".gguf"):
                    normalized_name = name.replace("\\", "/")
                    files.append(f"{folder_key}/{normalized_name}")
        except Exception:
            continue
    return files


def _resolve_gguf_file(gguf_model, gguf_file_path):
    path = str(gguf_file_path).strip()
    if path:
        return os.path.abspath(os.path.expanduser(path))

    if gguf_model and gguf_model != GGUF_NONE:
        folder_name, file_name = gguf_model.replace("\\", "/").split("/", 1)
        return folder_paths.get_full_path_or_raise(folder_name, file_name)

    return ""


def _dtype_from_name(dtype):
    if dtype == "float16":
        return torch.float16
    if dtype == "bfloat16":
        return torch.bfloat16
    return torch.float32


def _device_from_name(device):
    if device == "cuda" and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load_transformers():
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    except Exception as exc:
        raise RuntimeError(
            "Anime PromptGen requires transformers. Install it in the ComfyUI Python environment. "
            "GGUF loading also requires the gguf package."
        ) from exc

    return AutoModelForCausalLM, AutoTokenizer, pipeline


@lru_cache(maxsize=4)
def _load_pipeline(model_id_or_path, tokenizer_id_or_path, gguf_file, dtype_name, device_name, local_files_only):
    AutoModelForCausalLM, AutoTokenizer, pipeline = _load_transformers()

    model_source = model_id_or_path.strip() or DEFAULT_MODEL_ID
    tokenizer_source = tokenizer_id_or_path.strip() or model_source
    dtype = _dtype_from_name(dtype_name)
    device = _device_from_name(device_name)

    model_kwargs = {"local_files_only": bool(local_files_only)}
    tokenizer_candidates = [(tokenizer_source, {"local_files_only": bool(local_files_only)})]
    if gguf_file:
        model_dir = os.path.dirname(gguf_file)
        filename = os.path.basename(gguf_file)
        model_source = model_source if model_source != DEFAULT_MODEL_ID else model_dir
        tokenizer_source = tokenizer_source if tokenizer_id_or_path.strip() else model_source
        model_kwargs["gguf_file"] = filename
        model_kwargs["local_files_only"] = True

        tokenizer_candidates = []
        if tokenizer_source == model_source or tokenizer_source == DEFAULT_TOKENIZER_ID:
            tokenizer_candidates.append((model_source, {"gguf_file": filename, "local_files_only": True}))
        if tokenizer_source != model_source:
            tokenizer_candidates.append((tokenizer_source, {"local_files_only": True}))

    tokenizer_errors = []
    tokenizer = None
    for candidate_source, candidate_kwargs in tokenizer_candidates:
        try:
            tokenizer = AutoTokenizer.from_pretrained(candidate_source, **candidate_kwargs)
            break
        except Exception as exc:
            tokenizer_errors.append(f"{candidate_source}: {exc}")

    if tokenizer is None:
        detail = "\n\n".join(tokenizer_errors)
        raise RuntimeError(
            "Anime PromptGen could not load a tokenizer locally. For GGUF models, put tokenizer files next to "
            "the GGUF file or set tokenizer_id_or_path to a local tokenizer folder that contains tokenizer.json, "
            "vocab.json/merges.txt, or equivalent files.\n\n"
            f"Tokenizer attempts:\n{detail}"
        )

    try:
        if tokenizer.pad_token is None:
            tokenizer.add_special_tokens({"pad_token": "[PAD]"})
    except Exception:
        pass

    try:
        model = AutoModelForCausalLM.from_pretrained(model_source, dtype=dtype, **model_kwargs)
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(model_source, torch_dtype=dtype, **model_kwargs)

    if len(tokenizer) > model.get_input_embeddings().num_embeddings:
        model.resize_token_embeddings(len(tokenizer))

    model.to(device)
    return pipeline("text-generation", model=model, tokenizer=tokenizer, device=0 if device == "cuda" else -1)


_register_gguf_folder()


class AnimePromptGen:
    @classmethod
    def INPUT_TYPES(cls):
        gguf_models = [GGUF_NONE] + sorted(_gguf_files())
        return {
            "required": {
                "prompt": ("STRING", {"default": "1girl, genshin", "multiline": True}),
                "model_id_or_path": ("STRING", {"default": DEFAULT_MODEL_ID}),
                "tokenizer_id_or_path": ("STRING", {"default": DEFAULT_TOKENIZER_ID}),
                "gguf_model": (gguf_models, {"default": GGUF_NONE}),
                "gguf_file_path": ("STRING", {"default": "", "placeholder": "Optional absolute path to a .gguf file"}),
                "max_length": ("INT", {"default": 76, "min": 1, "max": 4096}),
                "num_return_sequences": ("INT", {"default": 10, "min": 1, "max": 64}),
                "do_sample": ("BOOLEAN", {"default": True}),
                "repetition_penalty": ("FLOAT", {"default": 1.2, "min": 0.01, "max": 10.0, "step": 0.01}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.01, "max": 5.0, "step": 0.01}),
                "top_k": ("INT", {"default": 4, "min": 0, "max": 1000}),
                "early_stopping": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "seed": ("INT", {"default": -1, "min": -1, "max": 0xffffffffffffffff}),
                "dtype": (["float32", "float16", "bfloat16"], {"default": "float32"}),
                "device": (["auto", "cpu", "cuda"], {"default": "auto"}),
                "local_files_only": ("BOOLEAN", {"default": False}),
                "strip_input_prompt": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompts", "first_prompt")
    FUNCTION = "generate"
    CATEGORY = "utils/text"

    def generate(
        self,
        prompt,
        model_id_or_path,
        tokenizer_id_or_path,
        gguf_model,
        gguf_file_path,
        max_length,
        num_return_sequences,
        do_sample,
        repetition_penalty,
        temperature,
        top_k,
        early_stopping,
        seed=-1,
        dtype="float32",
        device="auto",
        local_files_only=False,
        strip_input_prompt=False,
    ):
        if int(seed) >= 0:
            torch.manual_seed(int(seed))
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(int(seed))

        resolved_device = "cuda" if device == "auto" and torch.cuda.is_available() else device
        if resolved_device == "auto":
            resolved_device = "cpu"

        gguf_file = _resolve_gguf_file(gguf_model, gguf_file_path)
        if gguf_file and not os.path.isfile(gguf_file):
            raise FileNotFoundError(f"GGUF file not found: {gguf_file}")

        generator = _load_pipeline(
            str(model_id_or_path),
            str(tokenizer_id_or_path),
            gguf_file,
            dtype,
            resolved_device,
            bool(local_files_only),
        )

        outs = generator(
            str(prompt),
            max_length=int(max_length),
            num_return_sequences=int(num_return_sequences),
            do_sample=bool(do_sample),
            repetition_penalty=float(repetition_penalty),
            temperature=float(temperature),
            top_k=int(top_k),
            early_stopping=bool(early_stopping),
            pad_token_id=generator.tokenizer.pad_token_id,
        )

        prompts = []
        for out in outs:
            text = str(out["generated_text"]).replace("  ", "").rstrip(",")
            if strip_input_prompt and text.startswith(prompt):
                text = text[len(prompt):].lstrip(" ,")
            prompts.append(text)

        return ("\n\n".join(prompts), prompts[0] if prompts else "")


NODE_CLASS_MAPPINGS = {
    "AnimePromptGen": AnimePromptGen,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimePromptGen": "Anime PromptGen",
}
