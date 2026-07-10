# Models Inventory

## Base Models
- `Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24` (Russian/English)
- `uzlm/alloma-3B-Instruct` (Uzbek)
- `kyutai/mimi` / Moshi (Audio)

## LoRA Adapters
- `ru_all`: Russian phonetics adapter
- `aziza-adapter-final-uz`: Uzbek language adapter

## Languages Supported
- English (EN)
- Russian (RU)
- Uzbek (UZ)

## Datasets
Located in `training/datasets/` and `training/personaplex-finetune/`. Comprises bilingual conversational data and phonetic mappings.

## Scripts
- **Training**: `training/scripts/` (Rank, Alpha, Dropout tuning)
- **Evaluation**: `training/evaluation/`

## Runtime Configuration
Managed by PM2 (`configs/pm2/ecosystem.config.js`). Models are loaded in 8-bit/4-bit quantization using bitsandbytes, with GPU memory utilization configured per worker to avoid OOM.
